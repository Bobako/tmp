import datetime
import operator

import requests
import json

STORIES_USER_AGENT = "Instagram 123.0.0.21.114 (iPhone; CPU iPhone OS 11_4 like Mac OS X; en_US; en-US; scale=2.00; 750x1334) AppleWebKit/605.1.15"

parser = None
cached = {}

class Parser:
    session_id: int
    proxies: dict
    user_agent: str
    uids = dict()

    def __init__(self, login=None, password=None, session_id=None, proxy=None, user_agent=None):
        """При передаче логина и пароля происходит попытка входа. Если вход успешен, куки использоваться не будут.
        session_id - кукa sessionid, необходима чтобы избежать редиректа при большом кол-ве запросов.
        Желательно менять каждые несколько сотен запросов.
        proxies - прокси формата 'socks5h://127.0.0.1:9050'.
        user_agent - агент парсера. По умолчанию "Instagram 123.0.0.21.114 (iPhone; CPU iPhone OS 11_4 like Mac OS X; en_US; en-US; scale=2.00; 750x1334) AppleWebKit/605.1.15"
        Работает сасно, менять необходимости нет"""

        if session_id:
            self.cookies = {"sessionid": session_id}
        else:
            self.cookies = {}

        self.headers = {"Accept": "*/*",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
                        "Alt-Used": "www.instagram.com",
                        "Connection": "keep-alive",
                        "User-Agent": "Instagram 123.0.0.21.114 (iPhone; CPU iPhone OS 11_4 like Mac OS X; en_US;"
                                      " en-US; scale=2.00; 750x1334) AppleWebKit/605.1.15"}

        if user_agent:
            self.headers["User-Agent"] = user_agent
        if proxy:
            self.proxies = dict(http=proxy, https=proxy)
        else:
            self.proxies = {}
        if login and password:
            self.authorize(login, password)
        if proxy:
            self.test_proxy()

    def test_proxy(self):
        r = requests.get("http://icanhazip.com").text
        p = requests.get("http://icanhazip.com", proxies=self.proxies)
        if p.status_code != 200 or p.text == r:
            print(f"Proxy doesnt working and will not be used")
            self.proxies = {}
        else:
            print(f"Proxy connection via {p.text} established")

    def authorize(self, username, password):
        """Авторизоваться под именем {username} по паролю {password}.
        После успешного входа использует полученные куки"""

        url = "https://www.instagram.com/"
        login_url = "https://www.instagram.com/accounts/login/ajax/"
        headers = self.headers
        r = requests.get(url, headers=headers)
        csrf_token = r.cookies["csrftoken"]
        headers["X-CSRFToken"] = csrf_token
        cookies = r.cookies
        login_payload = {'username': username, 'password': password}
        login = requests.post(login_url, data=login_payload, allow_redirects=True, headers=headers, cookies=cookies)
        j = login.json()
        if j["authenticated"] and login.status_code == 200:
            self.cookies = login.cookies
            print(f"Login successful for {username}")
        else:
            print(f"Login failed for {username}")

    def __get_json(self, url, useragent=None):
        headers = self.headers
        if useragent:
            headers["User-Agent"] = useragent
        while True:
            r = requests.get(url, headers=headers, cookies=self.cookies, proxies=self.proxies)

            if r.status_code == 200:
                try:
                    j = r.json()
                except Exception:
                    return  # td
                    rotate_ip()
                else:
                    return j


            else:
                print(f"Request status code {r.status_code}, {r.text}")
                raise Exception()

    def __post_json(self, url, payload, useragent=None):
        headers = self.headers
        if useragent:
            headers["User-Agent"] = useragent
        r = requests.post(url, data=payload, headers=headers, cookies=self.cookies, proxies=self.proxies)

        if r.status_code == 200:
            try:
                return r.json()
            except json.decoder.JSONDecodeError:
                print("Instagram redirected to login page")
                raise Exception()
        else:
            print(f"Request status code {r.status_code}, {r.text}")
            raise Exception()

    def get_user_id(self, username):
        """Получить instagram id пользователся с именем {username}"""

        if username in self.uids:
            return self.uids[username]
        url = f"https://www.instagram.com/{username}/?__a=1"
        j = self.__get_json(url)
        print(j)
        input()
        uid = j["graphql"]["user"]["id"]
        self.uids[username] = uid
        return uid

    def get_posts_by_date(self, login, start_date=None, fin_date=None):
        """Получить список постов аккаунта с именем {login} загруженных между датами {start_date} и {fin_date}(дата и время снимка в секундах
         от начала эпохи).
         Формат возвращаемого значения: список словарей формата {id, urls(список адресов контента поста),
         caption(текст поста), likes (число лайков), comments(число комментов), timestamp(дата и время снимка в секундах
         от начала эпохи)}"""

        if not fin_date:
            fin_date = int(datetime.datetime.now().strftime("%s"))
        if not start_date:
            start_date = 1

        url = f"https://www.instagram.com/{login}/?__a=1"
        j = self.__get_json(url)
        user_id = j["graphql"]["user"]["id"]
        follows = j["graphql"]["user"]["edge_follow"]["count"]
        followed = j["graphql"]["user"]["edge_followed_by"]["count"]
        self.uids[login] = user_id

        nodes = [node["node"] for node in j['graphql']['user']['edge_owner_to_timeline_media']['edges']]
        has_next_page = j['graphql']['user']['edge_owner_to_timeline_media']['page_info']['has_next_page']
        cursor = ""
        if has_next_page:
            cursor = j['graphql']['user']['edge_owner_to_timeline_media']['page_info']['end_cursor']

        last_node_date = nodes[-1]["taken_at_timestamp"]

        while has_next_page and last_node_date > start_date:
            url = f"https://www.instagram.com/graphql/query/?query_hash=8c2a529969ee035a5063f2fc8602a0fd&variables=%7B%22id%22%3A%22{user_id}%22%2C%22first%22%3A{50}%2C%22after%22%3A%22{cursor}%22%7D"
            j = self.__get_json(url)
            nodes += [node["node"] for node in j['data']['user']['edge_owner_to_timeline_media']['edges']]
            has_next_page = j['data']['user']['edge_owner_to_timeline_media']['page_info']['has_next_page']
            if has_next_page:
                cursor = j['data']['user']['edge_owner_to_timeline_media']['page_info']['end_cursor']
            last_node_date = nodes[-1]["taken_at_timestamp"]

        posts = []
        post_count = 0
        video_count = 0
        likes = 0
        comments = 0
        views = 0
        for node in nodes:
            post = dict()
            post["id"] = node["id"]
            post["d"] = node["taken_at_timestamp"]
            post["code"] = node["shortcode"]
            post["likes"] = node["edge_media_preview_like"]["count"]
            post["comments"] = node["edge_media_to_comment"]["count"]
            if (post["id"] not in [post_n["id"] for post_n in posts]) and start_date < post["d"] < fin_date:
                posts.append(post)
                likes += node["edge_media_preview_like"]["count"]
                comments += node["edge_media_to_comment"]["count"]
                post_count += 1

        stats = {
            'following': follows,
            'followed': followed,
            'posts': post_count,
            'likes': likes,
            'comments': comments,
            'video views': views,
            'likes/post': likes/post_count if post_count else 0,
            'comments/post': comments/post_count if post_count else 0,
            'views/post': views/video_count if video_count else 0,
        }

        return posts, stats


def rotate_ip():
    pass


def get_proxy():
    pass


def get_posts(username, start, end, sort_by, order):
    global parser
    global cached
    if not parser:
        parser = Parser('aleksandr.shishiga', 'otvertka')
    if not start:
        start = 0
    if not end:
        end = 0
    print(datetime.datetime.fromtimestamp(start), datetime.datetime.fromtimestamp(end))
    if not ":".join([username, str(start), str(end)]) in cached:

        posts, stats = parser.get_posts_by_date(username, start, end)
        cached[":".join([username, str(start), str(end)])] = (posts, stats)
    else:
        posts, stats = cached[":".join([username, str(start), str(end)])]

    sort_posts(posts, sort_by)
    if order == 'desc':
        posts = posts[::-1]
    return posts, stats


def sort_posts(posts, sort_by):
    if sort_by == "posts":
        sort_by = "d"
    posts.sort(key=operator.itemgetter(sort_by))


if __name__ == '__main__':
    pass