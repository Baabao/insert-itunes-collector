from __future__ import absolute_import

import copy
import datetime
import gc
import os
import timeit
import traceback
from builtins import next, str
from functools import partial
from multiprocessing import Manager, Pool
from multiprocessing.managers import BaseProxy, DictProxy
from typing import Dict, List, Optional, Tuple, Union

from feedparser import FeedParserDict
from redis.exceptions import RedisError

from app.collector.db_sync import sync_tag_data_from_db
from app.collector.itunes_collection_handler import (
    create_itunes_data,
    get_artwork_url_600,
    get_collection_name,
    get_feed_url,
    get_genre_ids,
    remove_itunes_data,
    write_itunes_data,
)
from app.collector.itunes_tag_handler import find_itunes_tag, update_itunes_tag_data
from app.common.collection import is_empty_dict, sort_list_by_key
from app.common.comparsion import check_equal_string
from app.common.exceptions import (
    ExcludeItemError,
    FeedResultException,
    FeedResultFieldNotFoundError,
    FormatterException,
    ItunesDataError,
)
from app.common.inspect import calc_deco, diff_time
from app.concurrency_task import get_detail, get_top
from app.crawler import abort_wrapper, crawl_feeder
from app.db.deco import check_conn
from app.db.operations import (
    get_all_deleted_itunes_program,
    get_all_episode_by_program_v3,
    get_all_itunes_genre,
    get_all_itunes_producer,
    get_all_itunes_program,
    get_internal_category_mapping,
    get_itunes_episode,
    get_itunes_genre,
    get_itunes_program_v2,
    get_rssimport_program_by_rss_data,
    insert_count_entries,
    insert_episode,
    insert_itunes_genre,
    insert_itunes_program_itunes_genres,
    insert_producer,
    insert_program,
    insert_rank_data,
    insert_tag,
    update_program_itunes_internal_category,
    update_program_latest,
    update_program_recovery,
)
from app.feed_parser.formatter import string_formatter
from app.feed_parser.helper import (
    get_feed_author_email_field,
    get_feed_author_name_field,
    get_feed_data_uri_field,
    get_feed_description_description,
    get_feed_duration_field,
    get_feed_entries_field,
    get_feed_field,
    get_feed_img_url,
    get_feed_release_date_field,
    get_feed_tag_field,
    get_feed_title_field,
    is_good_feed_dict,
)
from config.constants import ITUNES_COLLECTION_PATH, ITUNES_TAGS_FILE_PATH, PROJECT_PATH
from config.loader import execution
from core.common.fs_utils import read_file, write_file
from core.common.string import is_empty_string, to_utf8_string, trim_string
from core.conf import ExecutionInterface
from core.db.utils import Error as DBError
from log_helper.async_logger import get_async_logger
from log_helper.utils import dir_attrs

logger = get_async_logger("main")


def get_exclude_program_list(file_path: str) -> List[str]:
    try:
        exclusion_file = read_file(file_path)
        exclusion_list = []
        for line in exclusion_file.split("\n"):
            if is_empty_string(line):
                continue
            collection_id, _ = line.split("#")
            exclusion_list.append(trim_string(to_utf8_string(collection_id)))
        return exclusion_list
    except (PermissionError, FileNotFoundError, OSError) as exc:
        logger.debug("file access error, file_path: %s, %s", file_path, exc)
        raise exc
    except Exception as exc:
        logger.error("unexpected error, %s", traceback.format_exc(10))
        raise Exception("Unexpected error, %s" % (exc,)) from exc


def update_exclude_program_list(file_path: str, program_string: str) -> str:
    exclusion_list = write_file(file_path, program_string, mode="a")
    return str(exclusion_list)


def get_collection_list_by_itunes_program() -> List[str]:
    return [program[1] for program in get_all_itunes_program()]


def get_deleted_collection_id_list_by_itunes_program() -> List[str]:
    return [program[1] for program in get_all_deleted_itunes_program()]


def get_itunes_genre_list() -> List[Dict]:
    return [
        {
            "id": genre_pk,
            "genre_id": genre_id,
            "name": genre_name,
            "enable": genre_enable,
        }
        for genre_pk, genre_id, genre_name, genre_enable in get_all_itunes_genre()
    ]


def get_available_itunes_genre_id_list() -> List[str]:
    itunes_genre_list = get_itunes_genre_list()
    genre_ids = ["26"]
    genre_ids += [
        genre["genre_id"]
        for genre in itunes_genre_list
        if isinstance(genre, dict) and genre.get("enable") and genre.get("genre_id")
    ]
    return genre_ids


def create_itunes_producer_dict(producer_list: List[Tuple]) -> Dict:
    return {i_p_id: p_id for i_p_id, p_id in producer_list}


def find_itunes_producer(
    producer_dict: Union[Dict, DictProxy], itunes_producer_id: str
) -> Tuple:
    return next(
        (
            (i_p_id, p_id)
            for i_p_id, p_id in list(producer_dict.items())
            if i_p_id == itunes_producer_id
        ),
        (None, None),
    )


def create_start_message() -> str:
    br = "########################################"
    new_line = "\n"

    messages = [br, "[App config]"]

    app = execution.config
    for attr in dir(app):
        if attr.startswith("_") or callable(getattr(app, attr)):
            continue
        messages.append(f"{attr}: {getattr(app, attr)}")

    messages += ["--------------------", "[Runner config]"]

    runner = execution.runner
    for attr in dir(runner):
        if attr.startswith("_") or callable(getattr(runner, attr)):
            continue
        messages.append(f"{attr}: {getattr(runner, attr)}")

    messages += [br]

    return new_line + f"{new_line}".join(messages)


@calc_deco()
def entry_point():
    itunes_tags_fp = ITUNES_TAGS_FILE_PATH
    process_num = execution.runner.process_num

    logger.info(create_start_message())

    manager = Manager()

    collection_dict = manager.dict()
    retry_dict = manager.dict()
    cost_list = manager.list()
    producer_dict = manager.dict()
    sleep_dict = manager.dict()

    logger.info("LOG SPOT 119 - get program and producer")

    collection_list = get_collection_list_by_itunes_program()

    deleted_collection_ids = get_deleted_collection_id_list_by_itunes_program()

    producer_dict.update(create_itunes_producer_dict(get_all_itunes_producer()))

    logger.info("update tag file")
    sync_tag_data_from_db(itunes_tags_fp)

    logger.info("LOG SPOT 131 - exec gc %s", gc.collect())
    logger.info("crawl itunes data start")

    # get itunes_genre_list from api
    genre_ids = get_available_itunes_genre_id_list()
    if not genre_ids:
        logger.info("itunes genre empty")
        return

    func = partial(get_top, collection_dict, retry_dict, cost_list, collection_list)
    pool = Pool(processes=process_num)
    results = pool.map(func, genre_ids)
    pool.close()
    pool.join()

    logger.info(
        "LOG SPOT 117 - crawl_cost: %s",
        str(sort_list_by_key(list(cost_list), "cost_time", 0, True)),
    )

    # check results, if any genre_id"s data empty, arrange it into lost_genres
    lost_genres = []
    for result in results:
        if result:
            for genre_id, top_data in list(result.items()):
                if not top_data:
                    lost_genres.append(genre_id)

    # retry block for genre
    logger.info("LOG SPOT 132 - exec gc %s", gc.collect())
    logger.info("LOG SPOT 115 - retry top_data count: %s", str(len(lost_genres)))

    while len(lost_genres) > 0:
        logger.info("LOG SPOT 116 - retry top_data: %s", str(lost_genres))
        for genre_id in copy.copy(lost_genres):
            logger.info("LOG SPOT 121 - retry genre_id: %s", str(genre_id))
            result = get_top(
                collection_dict, retry_dict, cost_list, collection_list, genre_id
            )
            if result:
                logger.info("LOG SPOT 122 - %s retry ok", str(genre_id))
                results.append({genre_id: result})
                lost_genres[:] = [g_id for g_id in lost_genres if g_id != genre_id]

    # retry block for collection
    logger.info("LOG SPOT 110 - retry_dict count: %s", len(retry_dict))

    if retry_dict:
        logger.info("LOG SPOT 111 - retry_dict happen %s", str(retry_dict))
        retry_count = 3
        while retry_count > 0:
            logger.info("LOG SPOT 120 - retry_count %s", str(retry_count))
            func_detail = partial(get_detail, collection_dict, retry_dict)
            retry_list = [c_id for c_id, _ in list(retry_dict.items())]
            pool = Pool(processes=process_num)
            pool.map(func_detail, retry_list)
            pool.close()
            pool.join()
            retry_count -= 1

    logger.info("LOG SPOT 133 - exec gc %s", gc.collect())
    logger.info("LOG SPOT 113 - save rank data")

    manager = Manager()
    sql_lock = manager.Lock()

    for data in results:
        if is_empty_dict(data):
            continue
        # always loop one time
        for genre_id, top_data in list(data.items()):
            try:
                # create rank data
                insert_rank_data(
                    category_id=genre_id,
                    data=top_data,
                    lock=sql_lock,
                    sleep_dict=sleep_dict,
                )
            except Exception as exc:
                logger.info("create %s rank data error: %s", genre_id, exc)

    collection_ids = [
        collection_id for collection_id, _ in list(collection_dict.items())
    ]

    logger.info("LOG SPOT 134 - exec gc %s", gc.collect())
    logger.info("LOG SPOT 114 - save new program")

    async_dict = {}
    pool = Pool(processes=process_num)
    for collection_id in collection_ids:
        async_job = pool.apply_async(
            handle_create_timeout,
            (
                sql_lock,
                sleep_dict,
                collection_dict,
                collection_list,
                producer_dict,
                collection_id,
                deleted_collection_ids,
            ),
        )
        async_dict[collection_id] = async_job

    pool.close()
    pool.join()

    for collection_id, async_job in list(async_dict.items()):
        try:
            async_job.get(timeout=500)

        except Exception as e:
            logger.info(
                "LOG SPOT 118 - handle_new_program! %s occur error: %s",
                collection_id,
                str(e),
            )


def handle_create_timeout(
    lock: BaseProxy,
    sleep_dict: DictProxy,
    collection_dict: DictProxy,
    collection_list: List,
    producer_dict: DictProxy,
    collection_id: str,
    deleted_collection_ids,
):
    timeout = execution.config.create_program_timeout

    logger.debug("timeout: %s", timeout)

    abort_wrapper(
        handle_create,
        lock,
        sleep_dict,
        collection_dict,
        collection_list,
        producer_dict,
        collection_id,
        deleted_collection_ids,
        timeout=timeout,
    )

    return None


@check_conn(end_connection=True)
def handle_create(
    lock: BaseProxy,
    sleep_dict: DictProxy,
    collection_dict: DictProxy,
    collection_list: List,
    producer_dict: DictProxy,
    collection_id: str,
    deleted_collection_ids: List,
):
    try:
        rss_time_limit = execution.config.fetch_rss_timeout
        insert_time_limit = execution.config.insert_episode_timeout
        exclude_program_list = get_exclude_program_list(
            file_path=os.path.join(
                PROJECT_PATH, execution.config.exclude_program_list_file_path
            )
        )
        itunes_collection_path = ITUNES_COLLECTION_PATH
        itunes_tags_file_path = ITUNES_TAGS_FILE_PATH

        start_time = timeit.default_timer()

        collection_id = string_formatter(collection_id)

        # check collection does same in baabao program
        exist = check_exclusion_collection(exclude_program_list, collection_id)
        if exist:
            raise ExcludeItemError(f"{collection_id} is in the exclusion list.")

        data = collection_dict.get(collection_id, None)
        if data is None:
            return None

        if collection_id in collection_list:
            logger.info("exist_collection! %s already exist", collection_id)
            return None

        itunes_genre_list = get_itunes_genre_list()
        if not itunes_genre_list:
            logger.info("itunes genre empty, exit")
            return

        internal_categories = get_internal_category_mapping()
        if not internal_categories:
            logger.info("itunes internal category non exist")

            return

        logger.info("start_collection! %s", collection_id)

        # -------------------- start crawl rss --------------------
        # crawl feeder
        feed_url = get_feed_url(data)

        logger.info(
            "crawl_feeder! start_crawl! collection %s, feed_url %s",
            collection_id,
            feed_url,
        )

        feed_result: FeedParserDict = crawl_feeder(url=feed_url)
        if not is_good_feed_dict(feed_result):
            logger.info("crawl_feeder func something error")
            return None

        if not feed_result.entries:
            raise Exception("ep_empty! %s does not have episode" % (collection_id,))

        logger.info(
            "crawl_feeder! end_crawl! collection_id %s, feed_url %s, cost %s sec",
            collection_id,
            feed_url,
            diff_time(start_time),
        )

        # -------------------- end crawl rss --------------------

        # -------------------- start insert producer --------------------
        # check this artist id exist
        # Notice: use collection_id to make producer instead of artistId from iTunes
        artist_id = collection_id
        i_producer_id, producer_id = find_itunes_producer(producer_dict, artist_id)

        # not exist, create
        if i_producer_id is None:
            # create producer
            nick_name = data.get("artistName")
            if not nick_name:
                raise Exception("artist %s does not have artist name" % (artist_id,))

            producer_id = insert_producer(
                artist_id=artist_id,
                nick_name=nick_name,
                lock=lock,
                sleep_dict=sleep_dict,
            )
            logger.info(
                "LOG SPOT 101 - insert_producer, producer_id: %s", str(producer_id)
            )

            producer_dict.update({artist_id: producer_id})
        else:
            logger.info(
                "LOG SPOT 113 - new collection id (%s) is existed producer i_p_id  ",
                artist_id,
            )

        # -------------------- end insert producer --------------------
        # todo: change tag_mapper_list source with API
        # todo: allow save m to m relation for category tag

        # -------------------- start insert program tag --------------------
        # create tag

        genre_list = get_genre_ids(data)
        name_set = set()
        # default: 4446 talk show"s id
        tag_id = "4446"
        for genre_id in genre_list:
            try:
                # search
                # name = tag_mapper_dict.get(int(genre_id))
                name = next(
                    (
                        name
                        for c_id, name, g_id in internal_categories
                        if g_id == genre_id
                    ),
                    None,
                )
                if name is None:
                    continue

                exist_tag: Dict = find_itunes_tag(itunes_tags_file_path, tag_name=name)
                if is_empty_dict(exist_tag):
                    tag_id = insert_tag(name=name, lock=lock, sleep_dict=sleep_dict)
                    logger.info("LOG SPOT 102 [insert_tag] tag id: %s", str(tag_id))
                else:
                    tag_id = exist_tag.get("id", tag_id)

                name_set.add(name)

                if len(name_set) == 1:
                    break

            except Exception as e:
                logger.info("tag_error! %s", str(e))
        # -------------------- end insert program tag --------------------

        feed_field = get_feed_field(feed_result)
        if feed_field is None:
            raise FeedResultException("Empty feed field")
        try:
            feed_image = get_feed_img_url(feed_field)
        except FeedResultFieldNotFoundError as exc:
            logger.info("get_feed_img_url can not fetch image url, %s", exc)
            feed_image = None

        feed_entries = get_feed_entries_field(feed_result)

        episode_list = []
        if collection_id not in deleted_collection_ids:
            # 只在一般 insert flow 進行，如果是已刪除的 itunes program, 因為不會用到這包 episode_list 故不再浪費時間跑這段
            # -------------------- start convert episode --------------------
            for entry in feed_entries:
                try:
                    episode_dict = handle_new_entry(
                        lock=lock,
                        sleep_dict=sleep_dict,
                        entry=entry,
                        collection_id=collection_id,
                        feed_image=feed_image,
                    )
                    if episode_dict is not None:
                        episode_list.append(episode_dict)

                except FeedResultException as exc:
                    logger.info(
                        "handle_new_entry field not found, collection_id: %s, %s",
                        collection_id,
                        exc,
                    )

                except FormatterException as exc:
                    logger.info(
                        "handle_new_entry convert error, collection_id: %s, %s",
                        collection_id,
                        exc,
                    )

                except Exception as _:
                    logger.error(
                        "handle_new_entry unexpected error, collection_id: %s, %s",
                        collection_id,
                        traceback.format_exc(10),
                    )

                # the compare second should be less than half of aborting second, e.g aborting 300 -> lte 150
                if timeit.default_timer() - start_time > rss_time_limit:
                    break
            # -------------------- end convert episode --------------------

            if not episode_list:
                logger.info(
                    "empty_episode_error! %s does not have invalid episode",
                    collection_id,
                )
                return None

        # -------------------- start insert program --------------------
        try:
            title = get_collection_name(data)
            image_url = get_artwork_url_600(data)
        except ItunesDataError as exc:
            logger.info("get specific field error, %s", exc)
            return None

        try:
            rss_producer_name = get_feed_author_name_field(feed_field)
            rss_email = get_feed_author_email_field(feed_field)
        except FeedResultException as _:
            rss_producer_name = None
            rss_email = None

        new_program_rss_data = {
            "email": rss_email,
            "artistName": rss_producer_name,
            "feedUrl": get_feed_url(data),
        }

        # rss import check, condition: (1)match rss_url or (2)match email, name and program title
        (
            rssimport_program_id,
            rssimport_program_title,
        ) = get_rssimport_program_by_rss_data(
            rss_url=data.get("feedUrl"),
            release_status="immediate",
            producer_name=rss_producer_name,
            program_title=title,
            producer_email=rss_email,
        )

        if rssimport_program_id:
            logger.info(
                "[handle_create] %s %s detected a rss_import one(id:%s)",
                collection_id,
                title,
                rssimport_program_id,
            )
            # save to exclusion
            #  Note. 之後 rss import 節目若又刪除， itunes 也不會再將其爬入，因 exclusion list 目前沒有移出機制，相關 TODO 請參考 add_row_into_exclusion_list 的 Docs
            add_row_into_exclusion_list(
                collection_id=collection_id,
                message="%s (Rss Import Program Id %s)(insert daemon)"
                % (rssimport_program_title, rssimport_program_id),
            )
            return None

        if collection_id in deleted_collection_ids:
            # try recovery process
            return recovery_one_itunes_program(
                collection_id=collection_id,
                feed_entries=feed_entries,
                lock=lock,
                sleep_dict=sleep_dict,
            )

        program_id, itunes_program_id = insert_program(
            producer_id=producer_id,
            i_producer_id=artist_id,
            tag_id=tag_id,
            collection_id=collection_id,
            title=title,
            image_url=image_url,
            new_program_rss_data=new_program_rss_data,
            lock=lock,
            sleep_dict=sleep_dict,
        )
        logger.info(
            "LOG SPOT 103 - insert_program program_id: %s ; itunes_program_id: %s",
            str(program_id),
            str(itunes_program_id),
        )
        # -------------------- end insert program --------------------

        # -------------------- start insert itunes program itunes genres --------------------
        itunes_program_itunes_genres_set = []
        valid_genre_ids = []
        valid_genre_names = []
        for num, genre_id in enumerate(genre_list):
            itunes_genre = next(
                (
                    itunes_genre
                    for itunes_genre in itunes_genre_list
                    if str(itunes_genre.get("genre_id")) == str(genre_id)
                ),
                None,
            )
            if itunes_genre is None:
                if int(genre_id) == 26:
                    continue

                # todo: may sent the update info email to baabao
                try:
                    genre_names = data.get("genres", [])
                    itunes_genre_name = genre_names[num]
                except Exception as e:
                    logger.info("fetch_genre_name_error! %s, %s", genre_id, str(e))
                    continue

                itunes_genre_id, _ = get_itunes_genre(genre_id=genre_id)
                if itunes_genre_id is None:
                    itunes_genre_id = insert_itunes_genre(
                        lock=lock,
                        sleep_dict=sleep_dict,
                        genre_id=genre_id,
                        name=itunes_genre_name,
                    )
                    logger.info(
                        "LOG SPOT 104 - insert_itunes_genre, itunes_genre_id: %s",
                        str(itunes_genre_id),
                    )

            else:
                itunes_genre = next(
                    (
                        itunes_genre
                        for itunes_genre in itunes_genre_list
                        if str(itunes_genre.get("genre_id")) == str(genre_id)
                    ),
                    None,
                )
                if not itunes_genre:
                    continue

                itunes_genre_id = itunes_genre.get("id")
                itunes_genre_name = itunes_genre.get("name")

            itunes_program_itunes_genres_set.append(
                (itunes_program_id, itunes_genre_id)
            )
            valid_genre_ids.append(genre_id)
            valid_genre_names.append(itunes_genre_name)

        insert_itunes_program_itunes_genres(
            lock=lock, sleep_dict=sleep_dict, argslist=itunes_program_itunes_genres_set
        )
        # -------------------- end insert itunes program itunes genres --------------------

        # -------------------- start update program about itunes internal category id --------------------

        use_internal_categories = [
            i_category
            for i_category in internal_categories
            if i_category[2] in genre_list
        ]
        use_internal_categories.sort(key=lambda d: d[0], reverse=True)
        internal_category = use_internal_categories[0]

        update_program_itunes_internal_category(
            lock=lock,
            sleep_dict=sleep_dict,
            program_id=program_id,
            category_id=internal_category[0],
        )
        logger.info(
            "LOG SPOT 105 program_id: %s ; itunes_internal_category_id: %s",
            str(program_id),
            str(internal_category[0]),
        )

        # -------------------- end update program about itunes internal category id --------------------

        file_episode_list = []

        # -------------------- start insert episode --------------------
        for epi in episode_list:
            try:
                ep_id = insert_episode(
                    title=epi.get("episode_title"),
                    description=epi.get("episode_description"),
                    data_uri=epi.get("data_uri"),
                    program_id=program_id,
                    i_program_id=collection_id,
                    duration=epi.get("duration"),
                    release_date=epi.get("release_date"),
                    tags=epi.get("tags"),
                    img_url=epi.get("img_url"),
                    lock=lock,
                    sleep_dict=sleep_dict,
                )
                logger.info("LOG SPOT 106 - insert_episode, ep_id: %s", str(ep_id))

                file_episode_list.append(
                    {
                        "ep_id": ep_id,
                        "data_uri": epi.get("data_uri"),
                        "episode_title": epi.get("episode_title"),
                        "episode_description": epi.get("episode_description"),
                        "img_url": epi.get("img_url"),
                        "release_date": epi.get("release_date"),
                    }
                )

                # the compare second should be less than aborting second subtract sql lock second, e.g 300 - (30 x 2)
                if timeit.default_timer() - start_time > insert_time_limit:
                    break

            except Exception as e:
                logger.info(
                    "insert_episode_error! %s, %s insert error: %s",
                    collection_id,
                    epi.get("data_uri"),
                    str(e),
                )
        # -------------------- end insert episode --------------------

        # -------------------- start insert itunes statistic --------------------
        insert_count_entries(
            collection_id=collection_id,
            program_id=program_id,
            producer_id=producer_id,
            episode_count=len(file_episode_list),
            lock=lock,
            sleep_dict=sleep_dict,
        )
        logger.info("LOG SPOT 107 - count epi, count:%s", str(len(file_episode_list)))

        # -------------------- end insert itunes statistic --------------------

        file_episode_list.sort(
            key=lambda d: datetime.datetime.strptime(
                d["release_date"], "%Y/%m/%d %H:%M:%S"
            ),
            reverse=True,
        )

        # -------------------- start update program about count --------------------
        update_program_latest(
            program_id=program_id,
            episode_dict=file_episode_list[0],
            lock=lock,
            sleep_dict=sleep_dict,
        )
        # -------------------- end update program about count --------------------

        # -------------------- start generate file --------------------
        itunes_data = create_itunes_data(
            feed_url,
            title,
            image_url,
            file_episode_list,
            valid_genre_ids,
            valid_genre_names,
        )

        try:
            write_itunes_data(itunes_collection_path, collection_id, itunes_data)

        except Exception as e:
            remove_itunes_data(itunes_collection_path, collection_id)
            logger.error(
                "generate_file_error! %s generate error: %s", collection_id, str(e)
            )
        # -------------------- end generate file --------------------

        logger.info(
            "end_collection! %s cost %s sec", collection_id, diff_time(start_time)
        )

    except FeedResultException as exc:
        logger.info("feed result error, collection_id: %s, %s", collection_id, exc)

    except ItunesDataError as exc:
        logger.info("itunes data error, collection_id: %s, %s", collection_id, exc)

    except ExcludeItemError as exc:
        logger.info("exclude item error, collection_id: %s, %s", collection_id, exc)

    except DBError as exc:
        logger.info("database occur error, collection_id: %s, %s", collection_id, exc)

    except RedisError as exc:
        logger.info("redis occur error, collection_id: %s, %s", collection_id, exc)

    except (TypeError, ValueError) as exc:
        logger.info("incorrect value, collection_id: %s, %s", collection_id, exc)

    except Exception as _:
        logger.error(
            "unexpected error, collection_id: %s, %s",
            collection_id,
            traceback.format_exc(10),
        )


# fix - add feed.image arg for compare entry.image
def handle_new_entry(
    lock, sleep_dict, entry, collection_id, feed_image
) -> Optional[Dict]:
    itunes_tags_file_path = ITUNES_TAGS_FILE_PATH

    # require fields
    data_uri = get_feed_data_uri_field(entry)
    title = get_feed_title_field(entry)
    release_date = get_feed_release_date_field(entry)
    duration = get_feed_duration_field(entry)

    # allow empty fields
    try:
        description = get_feed_description_description(entry)
    except (FeedResultFieldNotFoundError, IndexError) as exc:
        logger.debug("description not found, %s", exc)
        description = ""

    try:
        # compare entry.image is same as feed.image, if not, then entry has alone episode cover.
        img_url = get_feed_img_url(feed_field=entry)
        image_url = img_url if img_url != feed_image else None
    except FeedResultFieldNotFoundError as exc:
        logger.debug("img_url not found, %s", exc)
        image_url = feed_image

    try:
        tags = get_feed_tag_field(entry)
    except (FeedResultFieldNotFoundError, FormatterException) as exc:
        logger.debug("tags not found, %s", exc)
        tags = []

    itunes_episode = get_itunes_episode(data_uri=data_uri, collection_id=collection_id)
    if itunes_episode:
        logger.info(
            "exist data_uri, collection_id: %s, data_uri: %s", collection_id, data_uri
        )
        return None

    logger.info(
        "start convert entry, collection_id: %s, data_uri: %s", collection_id, data_uri
    )

    # -------------------- start insert episode tag -------------------
    tag_ids = set()
    update_tags = []
    # just make five tag
    for tag in tags[:5]:
        try:
            exist_tag = find_itunes_tag(itunes_tags_file_path, tag_name=tag)
            if exist_tag is None:
                # if exist in update_tags, continue to skip
                if next((t for t in update_tags if t.get("name") == tag), None):
                    continue
                tag_id = insert_tag(name=tag, lock=lock, sleep_dict=sleep_dict)
                logger.info("LOG SPOT 112 - [insert_tag] tag id: %s", str(tag_id))
            else:
                tag_id = (exist_tag.get("id"),)

            tag_ids.add(tag_id)
            update_tags.append({"id": tag_id[0], "name": tag})

        except Exception as e:
            logger.info("tag_error! %s", str(e))

    update_itunes_tag_data(itunes_tags_file_path, update_tags)
    # -------------------- end insert episode tag -------------------

    logger.info(
        "end convert entry, collection_id: %s, data_uri: %s", collection_id, data_uri
    )

    return {
        "data_uri": data_uri,
        "episode_title": title,
        "episode_description": description,
        "duration": duration,
        "release_date": release_date,
        "tags": list(tag_ids),
        "img_url": image_url,
    }


def check_exclusion_collection(exclusion_list: List, collection_id: str) -> bool:
    for exclusion_id in exclusion_list:
        if check_equal_string(collection_id, exclusion_id):
            return True
    return False


def recovery_one_itunes_program(collection_id, feed_entries, lock, sleep_dict):
    """
    嘗試復原一個節目

    collection_id String collection id
    feed_entries  FeedParser 物件的 entries 屬性

    """
    if not collection_id or not feed_entries:
        logger.info(
            "[recovery_one_itunes_program] input empty. collection_id %s, feed_entries %s",
            str(collection_id),
            str(feed_entries),
        )
        return None

    logger.info("[recovery_one_itunes_program] start %s", collection_id)

    # feed_entries -> parsed_entries (不使用 daemon 做好的 episode list，因 episode list 可能不完整，來自 insert daemon 的 timeout 限制與 handle entry 時長)
    parsed_entries = []
    for entry in feed_entries:
        try:
            # get url way in handle_new_entry
            data_uri = get_feed_data_uri_field(entry)
            if data_uri:
                parsed_entries.append({"data_uri": data_uri})
        except FeedResultException as exc:
            logger.info(
                "convert data_uri error, collection_id: %s, %s", collection_id, exc
            )
        except Exception as exc:
            logger.error("unexpected error, collection_id: %s, %s", collection_id, exc)

    logger.info(
        "[recovery_one_itunes_program] %s parsed entries count %s",
        collection_id,
        str(len(parsed_entries)),
    )

    # collection check and find program_id
    program_id, i_p_id, program_title = get_itunes_program_v2(
        collection_id=collection_id, release_status="deleted"
    )
    if not program_id:
        logger.info(
            "[recovery_one_itunes_program] collection_id %s not match to any deleted program"
            % collection_id
        )
        return None

    logger.info(
        "[recovery_one_itunes_program] collection_id %s found program id: %s",
        collection_id,
        program_id,
    )

    # 先 拉出全部 episode
    deleted_episdoes = get_all_episode_by_program_v3(
        program_id=program_id, release_status="deleted"
    )

    # for loop rss entries ，跟 deleted_episdoes 比對，找出 episode id
    recovery_episode_ids, recovery_episodes = find_recovery_episodes(
        parsed_entries=parsed_entries, deleted_episodes=deleted_episdoes
    )

    logger.info(
        "[recovery_one_itunes_program] program %s - recovery episode ids: %s",
        program_id,
        str(recovery_episode_ids),
    )

    # 計算 latest episdoe
    latest_episode_id, latest_episode_release_date = find_latest_episode(
        episodes=recovery_episodes
    )

    episode_count = len(recovery_episodes)
    logger.info(
        "[recovery_one_itunes_program] program %s - episode_count: %s, latest episode id: %s, release_date: %s",
        program_id,
        episode_count,
        latest_episode_id,
        latest_episode_release_date,
    )

    # 寫入
    update_program_recovery(
        program_id=program_id,
        collection_id=collection_id,
        episode_ids=recovery_episode_ids,
        latest_episode_id=latest_episode_id,
        latest_episode_release_date=latest_episode_release_date,
        episode_count=episode_count,
        lock=lock,
        sleep_dict=sleep_dict,
    )
    logger.info(
        "[recovery_one_itunes_program] program %s %s complete recovery",
        program_id,
        collection_id,
    )
    return True


# TODO: exclusion list 未來考慮移到某個儲存體，不要再採 local file
# 原因
#     一、 每次部署時，local 多的 collection id 有被蓋掉的風險 (因為會以 commit 版本部署，未 commit 者均有遺失風險)
#     -> 蓋掉可能帶來的風險： 蓋掉後， insert daemon 會重新對某個 collection id 做一次是否已有 RSS Import 節目的判斷
#         -> 若此時，剛好 RSS 內 製作人名稱、節目名稱、email 有變動，且 rss import daemon 還來不及把他們更新回 DB，則有可能會沒找到，進而 recovery 這個 iTunes 節目。
#     二、 RSS import 節目若再次刪除後， iTunes 也不會再次收錄該節目 (因為 exclusion list 沒有移除機制)
#
# 實作
#     1. 另有儲存體儲存 exclusion list
#     2. 除 collection id list 外，應能儲存刪除的原因，以及必要的相關資訊，例如 RSS import Program Id，以利未來如需移出 list 時，可做依據
#     3. 可採 boolean flag 做 Soft Delete，不要 Hard Delete
def add_row_into_exclusion_list(collection_id=None, message=None):
    """
    將某個 collection id 加入 exclusion list(local file)
    """

    logger.info("[add_row_into_exclusion_list] new exclusion for %s", collection_id)

    if not message:
        message = ""

    if collection_id:
        new_exclude_collection_string = f"{collection_id}  # {message}\n"

        update_exclude_program_list(
            os.path.join(PROJECT_PATH, execution.config.exclude_program_list_file_path),
            new_exclude_collection_string,
        )

        logger.info(
            "[add_row_into_exclusion_list] new exclusion added. %s",
            new_exclude_collection_string,
        )
        return True

    return None


def find_recovery_episodes(parsed_entries, deleted_episodes):
    recovery_episode_ids = []
    recovery_episodes = []
    if not parsed_entries or not deleted_episodes:
        return recovery_episode_ids, recovery_episodes

    for parsed_entry in parsed_entries:
        try:
            for deleted_episode in deleted_episodes:
                # deleted_episdoe [0] id, [1] title, [2] data_uri, [3] release_date, [4] desc
                episode_id = deleted_episode[0]
                episode_data_uri = deleted_episode[2]
                episode_release_date = deleted_episode[3]
                if (
                    episode_id
                    and episode_data_uri
                    and episode_data_uri == parsed_entry.get("data_uri")
                ):
                    recovery_episode_ids.append(episode_id)
                    recovery_episodes.append(
                        {
                            "episode_id": episode_id,
                            "data_uri": episode_data_uri,
                            "release_date": episode_release_date,
                        }
                    )
                    logger.info(
                        "[find_recovery_episodes] episode %s matched data_uri %s",
                        deleted_episode[0],
                        deleted_episode[2],
                    )
                    # 因 deleted_episodes 是 order by id desc ，一找到就 break，代表找符合 data_uri 中最大者
                    break
                # else:
                #     ts_log("[find_recovery_episodes] episode %s NO matched one" % (deleted_episodes[0]))

        except Exception as e:
            logger.info(
                "[find_recovery_episodes][fail] find episode id fail, error: %s, parsed_entry: %s",
                str(e),
                str(parsed_entry),
            )

    return recovery_episode_ids, recovery_episodes


def find_latest_episode(episodes):
    """
    episodes: [{"episode_id": episode_id, "release_date": release_date}, ...]
    """
    latest_episode_id = None
    latest_episode_release_date = None

    if not isinstance(episodes, list):
        return latest_episode_id, latest_episode_release_date

    for episode in episodes:
        if latest_episode_release_date:
            if latest_episode_release_date < episode["release_date"]:
                latest_episode_id = episode["episode_id"]
                latest_episode_release_date = episode["release_date"]
        else:
            latest_episode_id = episode["episode_id"]
            latest_episode_release_date = episode["release_date"]

    return latest_episode_id, latest_episode_release_date


# [INFO] 2025-03-06 03:42:25 - runner:execute:22 - Job start time: 2025-03-06 03:42:25
#     collection_list = get_collection_list_by_itunes_program()
#   File "/src/app/main.py", line 118, in get_collection_list_by_itunes_program
#     return [program[1] for program in get_all_itunes_program()]
#   File "/src/app/db/operations.py", line 467, in get_all_itunes_program
#     with connection.cursor() as cursor:
#   File "/src/core/db/manager.py", line 210, in cursor
#     return self._cursor()
#   File "/src/core/db/manager.py", line 189, in _cursor
#     return self._prepare_cursor(self.create_cursor(name))
#   File "/src/core/db/manager.py", line 126, in create_cursor
#     cursor = self.connection.cursor()
# psycopg2.InterfaceError: connection already closed
