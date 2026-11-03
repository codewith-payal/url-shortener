import random

from locust import HttpUser, between, task

HOT_CODES = [f"f{i}" for i in range(1, 11)]       # 10 very popular links
ALL_CODES = [f"f{i}" for i in range(1, 1001)]     # the 1,000 fake links


class Visitor(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def open_short_link(self):
        # 90% of traffic goes to a few hot links, like in real life
        pool = HOT_CODES if random.random() < 0.9 else ALL_CODES
        code = random.choice(pool)
        self.client.get(f"/{code}", allow_redirects=False, name="/[code]")