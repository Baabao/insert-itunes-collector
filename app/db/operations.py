import json
import traceback
import uuid
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

from app.common.collection import is_empty_list
from app.common.exceptions import DatabaseInsertError, DatabaseRemoveError
from app.db.deco import check_conn
from app.db.formatter import program_rss_data_formatter
from app.db.limitation import sql_lock
from app.db.utils import get_random_string
from config.constants import DJANGO_CACHE_DB_NUMBER, ITUNES_GENRE_CACHE_TIMEOUT
from core.cache.deco import apply_cache
from core.db import connection, transaction
from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


@check_conn
def get_tag_by_greater_created(greater_date: str):
    query = """
        SELECT "products_tag"."id", "products_tag"."name", "products_tag"."created"
        FROM "products_tag"
        WHERE "products_tag"."created" >= %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (greater_date,))
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@apply_cache("itunes_genre", DJANGO_CACHE_DB_NUMBER, ITUNES_GENRE_CACHE_TIMEOUT)
@check_conn
def get_all_itunes_genre():
    """
    Get products_itunes_genre all genre data
        - the same as response of django api (baabao/products/view/category_api/view.py ItunesGenreView)
        - cache key and time follow above api
        - return a list instead of psycopg2 result due to cache format compatibility - this cache is the same as django

    """
    query = """
        SELECT id, genre_id, name, enable 
        FROM products_itunes_genre
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
        )
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@sql_lock
@check_conn
def insert_rank_data(category_id, data):
    data = json.dumps(data)
    query = """
        INSERT INTO "products_itunes_rank" ("category_id", "data")VALUES (%s, %s)
        RETURNING "products_itunes_rank"."id"
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (category_id, data))
        logger.debug("insert_rank_data: ", cursor.query)
        result = cursor.fetchone()
        if result is None:
            raise DatabaseInsertError("Insert Failed")
        return result[0]


@check_conn
def get_itunes_program_have_subscribers():
    """
    Get itunes programs that have subscribers.
        - for sort_itunes_program in head of update_daemon
    """
    query = """
        SELECT program_id
        FROM products_program_subscription
        INNER JOIN products_itunes_program 
        ON products_itunes_program.p_id=products_program_subscription.program_id
        INNER JOIN products_program 
        ON products_program.id=products_program_subscription.program_id
        WHERE products_program.release_status='immediate'
        GROUP BY products_program_subscription.program_id;
    """
    with connection.cursor() as cursor:
        cursor.execute(
            query,
        )
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@sql_lock
@check_conn
def insert_producer(artist_id, nick_name):
    """
    insert producer and itunes mapping table
    """
    now = datetime.now()
    password = "!" + get_random_string()
    user_account = uuid.uuid4().hex[:30]
    nick_name = nick_name
    user_name = str(artist_id) + "!" + nick_name[: (29 - len(str(artist_id)))]

    auth_user_query = """
        INSERT INTO "auth_user" ("password", "last_login", "is_superuser", "username", "first_name", "last_name", "email", "is_staff", "is_active", "date_joined") 
        VALUES (%s, NULL, false, %s, '', '', 'baabaoradio@gmail.com', false, true, %s) 
        RETURNING "auth_user"."id";
    """

    producer_query = """
        INSERT INTO "products_producer" ("auth_user_id", "user_account", "nick_name", "image_url",  "created", "modified", "been_validate", "been_onboarding", "been_promote", "origin", "been_mini_onboarding") 
        VALUES (%s, %s, %s, 'http://default.jpg',  %s, %s, true, false, false, 'itunes', false) 
        RETURNING "products_producer"."id"; 
    """

    itunes_producer_query = """
        INSERT INTO "products_itunes_producer" ("i_p_id", "p_id") 
        VALUES (%s, %s) 
        RETURNING "products_itunes_producer"."id"; 
    """

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # insert auth user first
                cursor.execute(auth_user_query, (password, user_name, now))
                logger.debug("insert_producer: auth_user ", cursor.query)

                auth_user_id = cursor.fetchone()
                if not auth_user_id:
                    raise DatabaseInsertError("Insert auth user failed")

                auth_user_id = auth_user_id[0]

                cursor.execute(
                    producer_query, (auth_user_id, user_account, nick_name, now, now)
                )
                logger.debug("insert_producer: products_producer ", cursor.query)

                producer_id = cursor.fetchone()
                if not producer_id:
                    raise DatabaseInsertError("Insert producer failed")

                producer_id = producer_id[0]

                cursor.execute(itunes_producer_query, (artist_id, producer_id))
                logger.debug("insert_producer: products_itunes_producer ", cursor.query)

                itunes_producer_id = cursor.fetchone()
                if not itunes_producer_id:
                    raise DatabaseInsertError("Insert itunes producer failed")

        return producer_id

    except (Exception, psycopg2.DatabaseError) as exc:
        logger.error(traceback.format_exc())
        raise DatabaseInsertError(exc)


@sql_lock
@check_conn
def insert_program(
    producer_id,
    i_producer_id,
    tag_id,
    collection_id,
    title,
    image_url,
    description="",
    new_program_rss_data=None,
):
    """
    insert program and itunes mapping table
    """
    now = datetime.now()

    new_rss_url, new_producer_name, new_email = program_rss_data_formatter(
        program_rss_data=new_program_rss_data
    )

    # add release_status for soft deleting since Nov 2020
    program_query = """
        INSERT INTO "products_program" ("title", "description", "image_url", "producer_id", "created", "modified", "origin", "listen_count", "message_count", "episode_count", "subscription_count", "rss_listen_count", "release_status", "mini_listen_count") 
        VALUES (%s, %s, %s, %s, %s, %s, 'itunes', 0, 0, 0, 0, 0, 'immediate', 0) 
        RETURNING "products_program"."id"; 
    """

    program_tag_query = """
        INSERT INTO "products_program_tags" ("program_id", "tag_id")VALUES (%s, %s)
        RETURNING "products_program_tags"."id";
    """

    itunes_program_query = """
        INSERT INTO "products_itunes_program" ("i_p_id", "p_id", "producer_id")VALUES (%s, %s, %s)
        RETURNING "products_itunes_program"."id";
    """

    new_program_rss_data_query = """
        INSERT INTO "products_program_rss_data" ("program_id", "rss_url", "email", "producer_name", "created", "modified") 
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING "products_program_rss_data"."id";
    """

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # insert program first
                cursor.execute(
                    program_query,
                    (title, description, image_url, producer_id, now, now),
                )
                logger.debug("insert_program: products_program ", cursor.query)

                program_id = cursor.fetchone()
                if not program_id:
                    raise DatabaseInsertError("Insert program failed")

                program_id = program_id[0]

                cursor.execute(program_tag_query, (program_id, tag_id))
                logger.debug("insert_program: products_program_tags ", cursor.query)

                program_tag_id = cursor.fetchone()
                if not program_tag_id:
                    raise DatabaseInsertError("Insert program tag failed")

                cursor.execute(
                    itunes_program_query, (collection_id, program_id, i_producer_id)
                )
                logger.debug("insert_program: products_itunes_program ", cursor.query)

                itunes_program_id = cursor.fetchone()
                if not itunes_program_id:
                    raise DatabaseInsertError("Insert itunes program failed")

                # program rss data
                cursor.execute(
                    new_program_rss_data_query,
                    (program_id, new_rss_url, new_email, new_producer_name, now, now),
                )
                logger.debug("insert_program: products_program_rss_data ", cursor.query)

                program_rss_data_id = cursor.fetchone()
                if not program_rss_data_id:
                    raise DatabaseInsertError("Insert Program Rss Data Failed")

        return program_id, itunes_program_id[0]

    except (Exception, psycopg2.DatabaseError) as exc:
        logger.error(traceback.format_exc())
        raise DatabaseInsertError(exc)


@sql_lock
@check_conn
def insert_tag(name):
    now = datetime.now()

    query = """
        INSERT INTO "products_tag" ("name", "created", "modified")VALUES (%s, %s, %s) 
        RETURNING "products_tag"."id"
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (name, now, now))
        logger.debug("insert_tag: ", cursor.query)

        tag_id = cursor.fetchone()
        if not tag_id:
            raise DatabaseInsertError("Insert Failed")

    return tag_id


@sql_lock
@check_conn
def insert_episode(
    title,
    description,
    data_uri,
    program_id,
    i_program_id,
    duration,
    release_date,
    tags,
    img_url,
):
    now = datetime.now()

    episode_query = """
        INSERT INTO "products_episode" ("title", "description", "img_url", "data_uri", "duration", "program_id", "release_date", "release_status", "created", "modified", "origin", "message_count", "reviewed_user_id") 
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'immediate', %s, %s, 'itunes', 0, -1) 
        RETURNING "products_episode"."id"
    """

    episode_tag_query = """
        INSERT INTO "products_episode_tags" ("episode_id", "tag_id")VALUES (%s, %s)
        RETURNING "products_episode_tags"."id";
    """

    itunes_episode_query = """
        INSERT INTO "products_itunes_episode" ("i_ep_id", "ep_id", "program_id")VALUES (%s, %s, %s)
        RETURNING "products_itunes_episode"."id";
    """

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    episode_query,
                    (
                        title,
                        description,
                        img_url,
                        data_uri,
                        duration,
                        program_id,
                        release_date,
                        now,
                        now,
                    ),
                )
                logger.debug("insert_episode: products_episode ", cursor.query)

                episode_id = cursor.fetchone()
                if not episode_id:
                    raise DatabaseInsertError("Insert episode failed")

                episode_id = episode_id[0]

                for tag in tags:
                    cursor.execute(episode_tag_query, (episode_id, tag))
                    logger.debug("insert_episode: products_episode_tags ", cursor.query)

                    episode_tag_id = cursor.fetchone()
                    if not episode_tag_id:
                        raise DatabaseInsertError("Insert episode tag failed")

                cursor.execute(
                    itunes_episode_query, (data_uri, episode_id, i_program_id)
                )
                logger.debug("insert_episode: products_itunes_episode ", cursor.query)

                itunes_episode_id = cursor.fetchone()
                if not itunes_episode_id:
                    raise DatabaseInsertError("Insert itunes episode failed")

        return episode_id

    except (Exception, psycopg2.DatabaseError) as e:
        logger.error("unexpected db error, %s", traceback.format_exc())
        raise DatabaseInsertError(e)


@check_conn
def get_itunes_episode(data_uri, collection_id):
    query = """
        SELECT "products_itunes_episode"."i_ep_id", "products_itunes_episode"."ep_id"
        FROM "products_itunes_episode"
        INNER JOIN "products_episode" ON "products_episode"."id"="products_itunes_episode"."ep_id"
        WHERE "products_itunes_episode"."i_ep_id"=%s AND "products_itunes_episode"."program_id"=%s
        AND "products_episode"."release_status"='immediate'
    """
    # TODO: Here, products_itunes_episode use link to be the i_ep_id because we think the link is a good value which not often change.
    #       But according to real data, link sometimes change, so it is not good enough.
    #       We need to find a new information or decide a new mapping relationship to be the new id value.

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                data_uri,
                collection_id,
            ),
        )
        logger.debug("get_itunes_episode: ", cursor.query)

        result = cursor.fetchone()
        if result:
            return result
        else:
            return None


@sql_lock
@check_conn
def insert_count_entries(collection_id, program_id, producer_id, episode_count):
    """
    insert program and itunes mapping table
    """
    now = datetime.now()

    statistic_query = """
        INSERT INTO "products_itunes_collectionstatistics" ("i_p_id", "p_id", "producer_id", "episode_count", "last_update") 
        VALUES (%s, %s, %s, %s, %s) 
        RETURNING "products_itunes_collectionstatistics"."id"; 
    """

    program_query = """
        UPDATE "products_program"
        SET "episode_count" = %s
        WHERE "products_program"."id" = %s
        RETURNING "products_program"."id"; 
    """

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # insert program first
                cursor.execute(
                    statistic_query,
                    (collection_id, program_id, producer_id, episode_count, now),
                )
                logger.debug(
                    "insert_count_entries: products_itunes_collectionstatistics ",
                    cursor.query,
                )

                statistic_id = cursor.fetchone()
                if not statistic_id:
                    # if raise error, then itunes collect statistics's wont insert
                    raise DatabaseInsertError("Insert statistic failed")

                cursor.execute(
                    program_query,
                    (
                        episode_count,
                        program_id,
                    ),
                )
                logger.debug("insert_count_entries: products_program ", cursor.query)

                program = cursor.fetchone()
                if not program:
                    # if raise error, then program's episode count wont update
                    raise DatabaseInsertError("Update program failed")

        return statistic_id[0]

    except (Exception, psycopg2.DatabaseError) as exc:
        logger.error("unexpected db error, %s", traceback.format_exc())
        raise DatabaseInsertError(exc) from exc


@check_conn
def get_all_itunes_program():
    """
    Get current itunes programs
        - program release_status condition use = immediate now. Notice it if definition of release_status changed
    """
    query = """
        SELECT "products_itunes_program"."id", "products_itunes_program"."i_p_id", "products_itunes_program"."p_id"
        FROM "products_itunes_program"
        INNER JOIN "products_program"
        ON "products_program"."id"="products_itunes_program"."p_id"
        WHERE "products_program"."release_status"='immediate'
        ORDER BY "products_itunes_program"."id"
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@check_conn
def get_all_itunes_producer():
    query = """
        SELECT "products_itunes_producer"."i_p_id", "products_itunes_producer"."p_id"
        FROM "products_itunes_producer"
        ORDER BY "products_itunes_producer"."id"
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@sql_lock
@check_conn
def update_program_latest(program_id, episode_dict):
    episode_id = episode_dict["ep_id"]
    release_date = episode_dict["release_date"]

    program_query = """
        UPDATE "products_program"
        SET "latest_episode_id" = %s, "latest_episode_released" = %s
        WHERE "products_program"."id" = %s
        RETURNING "products_program"."id";
    """

    with connection.cursor() as cursor:
        cursor.execute(program_query, (episode_id, release_date, program_id))
        logger.debug("update_program_latest: ", cursor.query)

        result = cursor.fetchone()
        if not result:
            raise DatabaseInsertError("Update Failed")


# todo: fix word
@sql_lock
@check_conn
def insert_itunes_program_itunes_genres(argslist):
    # e.g. argslist: [(itunes_program_id, itunes_genre_id), (1, 82),]

    query = """
        INSERT INTO "products_itunes_program_itunes_genres" ("itunesprogram_id", "itunesgenre_id") 
        VALUES %s
    """

    with connection.cursor() as cursor:
        execute_values(cur=cursor, sql=query, argslist=argslist)
        logger.debug("insert_itunes_program_ituens_genres: ", cursor.query)


@sql_lock
@check_conn
def insert_itunes_genre(genre_id, name):
    now = datetime.now()

    query = """
        INSERT INTO "products_itunes_genre" ("genre_id", "name", "enable", "created", "modified")
        VALUES (%s, %s, %s, %s, %s)
        returning "products_itunes_genre"."id"; 
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (genre_id, name, False, now, now))
        logger.debug("insert_itunes_genre: ", cursor.query)

        itunes_genre_id = cursor.fetchone()
        if not itunes_genre_id:
            raise DatabaseInsertError("Insert Failed")

    return itunes_genre_id


@check_conn
def get_itunes_genre(genre_id):
    query = """
        SELECT products_itunes_genre.id, products_itunes_genre.genre_id
        FROM products_itunes_genre
        WHERE genre_id = %s
        LIMIT 1;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (genre_id,))
        result = cursor.fetchone()
        if result:
            return result
        else:
            return None, None


@check_conn
def get_internal_category_mapping():
    query = """
        SELECT i.id, t.name, g.genre_id
        FROM products_itunes_internal_category AS i
        JOIN products_tag AS t ON t.id = i.tag_id
        LEFT JOIN products_itunes_genre AS g ON g.id= i.itunes_genre_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
        )
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@sql_lock
@check_conn
def update_program_itunes_internal_category(program_id, category_id):
    query = """
        UPDATE products_program
        SET itunes_internal_category_id=%s
        WHERE id=%s
        returning id;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                category_id,
                program_id,
            ),
        )
        logger.debug("update_program_itunes_internal_category: ", cursor.query)

        result = cursor.fetchone()
        if not result:
            raise DatabaseInsertError("Update Failed")


@check_conn
def get_all_deleted_itunes_program():
    """
    Get current itunes programs
        - program release_status condition use = immediate now. Notice it if definition of release_status changed
    """
    query = """
        SELECT "products_itunes_program"."id", "products_itunes_program"."i_p_id", "products_itunes_program"."p_id"
        FROM "products_itunes_program"
        INNER JOIN "products_program"
        ON "products_program"."id"="products_itunes_program"."p_id"
        WHERE "products_program"."release_status"='deleted'
        ORDER BY "products_itunes_program"."id"
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@check_conn
def get_itunes_program_v2(collection_id, release_status):
    query = """
        SELECT "products_program"."id",
        "products_itunes_program"."i_p_id", 
        "products_program"."title"
        FROM "products_program"
        INNER JOIN "products_itunes_program" ON "products_itunes_program"."p_id"="products_program"."id"
        WHERE "products_itunes_program"."i_p_id"=%s
        AND "products_program"."release_status"=%s
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (collection_id, release_status))
        result = cursor.fetchone()
        if result:
            return result
        else:
            return None, None, None


@check_conn
def get_rssimport_program_by_rss_data(
    rss_url, release_status, producer_name, program_title, producer_email
):
    """
    Try get Rss Import Program By RSS Data
    (1) rss_url
    or
    (2) producer_name, program_title and producer_email
        - notice: These 3 terms maybe NULL, but we no need consider IS NULL clause, because NULL is not an effective value for matching

    TODO
    ＊＊＊ Where Clause Missing Hit 討論 ＊＊＊
    ＊ 此 Function 使用於某個 iTunes 節目想找到對應的 RSS Import 節目

    ＊ 何時會用此 function 找 RSS Import 節目？
        (1) 某節目剛 rss import 完後，之後碰到的第一次 insert daemon 啟動，且該節目在 排行榜上或 scan opml 有匯入。
            -> 此時應該沒問題， rss_url OR email/ 節目名稱 / 製作人名稱 應該能符合
        (2) exclusion list，在很久之後有一天不小心被蓋掉。之後遇到的第一次啟動 insert daemon 時
            -> 有低機率遇上問題: 當下某個節目剛好 rss 有改東西 (email/ 節目名稱 / 製作人名稱)，而相關修改還來不及 update 回 db
               -> 治標 1： insert daemon 頻率降低， rss import daemon 頻率提升，降低問題遇上的機率
               -> 治標 2： 每次有新修改時 (也就是會有部署時)，記得手動將自動加入的 exclusion commit 到 git 內，確保沒有 exclusion list 蓋掉問題

    ＊ 何時 exclusion list 會被蓋掉
        exclusion list 以 git commit 在 code 內，所以每次部署時都會蓋掉 ec2 上 local file ，若欲保留需以人工複製並 commit

    ＊ 情境舉例：
         (1) 製作人在 八寶 /Apple 分別用兩個 rss url (兩個 url 等效，例如 SoundOn)，因此 rss_url 不會符合，要靠 email/ 節目名稱 / 製作人名稱 的條件
         (2) RSS 內改了 email 或 節目名稱 或 製作人名稱，之後 RSS Import Daemon 還沒把資料更新回 DB 之前 (Max 1 小時以內, RSS Import Daemon 每小時更新一次)
         (3) 此時，exclusion list 被蓋掉
         (4) insert daemon 在 RSS Import Daemon 啟動之前啟動

         綜合上述情境，則會遇到 rss_url OR email/ 節目名稱 / 製作人名稱 都不符合，使這個 iTunes 節目沒有 Match 到對應 RSS Import 節目

    ＊ 治標討論
        主要如上『治標 2』，部署前手動確保 exclusion list 不要蓋掉，則可一切正常。

    ＊ 其他治本討論
          考慮 exclusion list 移到某個儲存體，不採 local file，如此沒有部署覆蓋問題。 參考 itunes_job/scheduled.py def add_row_into_exclusion_list() 的 Docs

    """
    if not rss_url or not release_status:
        return None, None

    query = """
        SELECT "products_program"."id", "products_program"."title"
        FROM "products_program"
        INNER JOIN "products_program_rss_data" ON "products_program_rss_data"."program_id" = "products_program"."id"
        WHERE "products_program"."origin" = 'rss_import'
        AND "products_program"."release_status" = %s
        AND (
            ("products_program_rss_data"."rss_url" = %s) 
            OR 
            (
                "products_program_rss_data"."producer_name"=%s
                AND "products_program"."title"=%s
                AND "products_program_rss_data"."email"=%s
            )
        )
        LIMIT 1
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (release_status, rss_url, producer_name, program_title, producer_email),
        )
        result = cursor.fetchone()
        if result:
            return result
        else:
            return None, None


@check_conn
def get_all_episode_by_program_v3(program_id, release_status):
    query = """
        SELECT "products_episode"."id", "products_episode"."title", "products_episode"."data_uri", "products_episode"."release_date", "products_episode"."description"
        FROM "products_episode"
        WHERE "products_episode"."program_id"=%s AND "products_episode"."release_status"=%s
        ORDER BY "products_episode"."id" DESC
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (program_id, release_status))
        result = cursor.fetchall()
        if not is_empty_list(result):
            return result
        else:
            return []


@sql_lock
@check_conn
def update_program_recovery(
    program_id,
    collection_id,
    episode_ids,
    latest_episode_id,
    latest_episode_release_date,
    episode_count,
):
    """
    reverse proccess of update_program_full_deleted
    """
    nowtime = datetime.now()

    recovery_program_sql = """ 
        UPDATE "products_program"
        SET "latest_episode_id"=%s, "latest_episode_released"=%s, "episode_count"=%s, "release_status"='immediate', "modified"=%s
        WHERE "products_program"."id" = %s;
    """

    recovery_episode_sql = """ 
        UPDATE "products_episode"
        SET "release_status"='immediate', "modified"=%s
        WHERE "products_episode"."id" IN %s;
    """

    recovery_collectionstatistics_sql = """ 
        UPDATE "products_itunes_collectionstatistics" 
        SET "episode_count"=%s, "last_update"=%s
        WHERE "products_itunes_collectionstatistics"."i_p_id"=%s 
        AND "products_itunes_collectionstatistics"."p_id"=%s;
    """

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # recovery program
                cursor.execute(
                    recovery_program_sql,
                    (
                        latest_episode_id,
                        latest_episode_release_date,
                        episode_count,
                        nowtime,
                        program_id,
                    ),
                )
                logger.debug("update_program_recovery: products_program ", cursor.query)

                # recovery episdoes, skip if episode id list empty
                if episode_ids:
                    cursor.execute(recovery_episode_sql, (nowtime, tuple(episode_ids)))
                    logger.debug(
                        "update_program_recovery: products_episode ", cursor.query
                    )

                # recovery episode count data in collectionstatistics
                cursor.execute(
                    recovery_collectionstatistics_sql,
                    (episode_count, nowtime, collection_id, program_id),
                )
                logger.debug(
                    "update_program_recovery: products_itunes_collectionstatistics ",
                    cursor.query,
                )

    except (Exception, psycopg2.DatabaseError) as exc:
        logger.error(traceback.format_exc())
        raise DatabaseRemoveError(exc) from exc
