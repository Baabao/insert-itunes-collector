from html.parser import HTMLParser

from log_helper.async_logger import get_async_logger

logger = get_async_logger(__name__)


class CustomizedHTMLParser(HTMLParser):
    """
    參考
        - https://stackoverflow.com/a/55825140/14747164
        - https://stackoverflow.com/a/62180428/14747164
        - https://docs.python.org/zh-tw/3.8/library/html.parser.html
    """

    def __init__(self, *args, **kwargs):
        self.text = ""  # create instance property .text
        super().__init__(*args, **kwargs)  # parent init

    def reset(self):
        self.text = ""  # rest text
        super().reset()  # parent reset

    def handle_starttag(self, tag, attrs):
        """Encountered a start tag"""
        # # 需要時請自行打開註解以觀察 HTML 解析過程
        # print("Encountered a start tag:", tag)

    def handle_endtag(self, tag):
        """Encountered an end tag"""
        # # 需要時請自行打開註解以觀察 HTML 解析過程
        # print("Encountered an end tag :", tag)

    def handle_data(self, data):
        """Encountered content text"""
        # # 需要時請自行打開註解以觀察 HTML 解析過程
        # debug_msg = "Encountered content lasttag: %s, cdata: %s. data: %s" % (
        #     str(self.lasttag), str(self.cdata_elem in self.CDATA_CONTENT_ELEMENTS), str(data)
        # )
        # print(debug_msg)

        # 有效 str，而且不是 <script>, <style> 的內容才收錄
        # 這麼寫是因為剛好此 Package 行為上， script, style 兩種 tag 的內容歸為 CDATA ，所以剛好可以用 cdata_elem 來決定是否跳過，
        # 另一個屬性 self.lasttag 因為在 tag 結束時不會清除，所以不夠好用 (下面有測試案例)
        if (
            data
            and isinstance(data, str)
            and self.cdata_elem not in self.CDATA_CONTENT_ELEMENTS
        ):
            # Save to text property
            self.text += data
