import os.path
import pathlib
import re
import sys

import pytest
from funnylog2 import logger

from youqu3 import setting


class Run:
    __author__ = "mikigo <huangmingqiang@uniontech.com>"

    def __init__(
            self,
            workdir=None,
            path=None,
            keywords=None,
            tags=None,
            setup_plan=None,
            slaves=None,
            txt=None,
            reruns=None,
            job_start=None,
            job_end=None,
            pytest_opt=None,
            record_failed_num=None,
            start_case=None,
            interrupt_continue=None,
            order_execution=None,
            **kwargs,
    ):
        logger("INFO")

        self.workdir = workdir
        self.path = path
        self.keywords = keywords
        self.tags = tags
        self.setup_plan = setup_plan
        self.slaves = slaves
        self.txt = txt
        self.reruns = reruns
        self.job_start = job_start
        self.job_end = job_end
        self.pytest_opt = pytest_opt
        self.record_failed_num = record_failed_num
        self.start_case = start_case
        self.interrupt_continue = interrupt_continue
        self.order_execution = order_execution

        self.rootdir = pathlib.Path(".").absolute()
        self.report_path = self.rootdir / "report"
        self.html_report_path = self.report_path / "html"
        self.allure_data_path = self.html_report_path / "_data"
        self.allure_html_path = self.html_report_path / "html"
        self.json_report_path = self.report_path / "json"

        from funnylog2.config import config as funnylog2_config

        funnylog2_config.LOG_FILE_PATH = self.report_path

    @staticmethod
    def makedirs(dirs):
        pathlib.Path(dirs).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def set_recursion_limit(strings):
        len_tags = len(re.split("or |and |not ", strings))
        if len_tags >= 999:
            sys.setrecursionlimit(len_tags + 100)

    def read_tags_txt(self):
        youqu_tags_file = os.path.join(self.rootdir, "youqu-tags.txt")
        if os.path.exists(youqu_tags_file):
            with open(youqu_tags_file, "r", encoding="utf-8") as f:
                tags_txt = f.readlines()[0]
                return tags_txt
        return None

    def read_keywords_txt(self):
        youqu_keywords_file = os.path.join(self.rootdir, "youqu-keywords.txt")
        if os.path.exists(youqu_keywords_file):
            with open(youqu_keywords_file, "r", encoding="utf-8") as f:
                keywords_txt = f.readlines()[0]
                return keywords_txt
        return None

    def generate_cmd(self):
        cmd = ["pytest"]

        if self.path:
            cmd.append(self.path)

        keywords_txt = self.read_keywords_txt()
        if self.keywords:
            self.set_recursion_limit(self.keywords)
            cmd.extend(["-k", f"'{self.keywords}'"])
        elif self.txt and keywords_txt is not None:
            self.set_recursion_limit(keywords_txt)
            cmd.extend(["-k", f"'{keywords_txt}'"])

        tags_txt = self.read_tags_txt()
        if self.tags:
            self.set_recursion_limit(self.tags)
            cmd.extend(["-m", f"'{self.tags}'"])
        elif self.txt and tags_txt is not None:
            self.set_recursion_limit(tags_txt)
            cmd.extend(["-m", f"'{tags_txt}'"])

        if self.slaves:
            cmd.extend(["--slaves", f"'{self.slaves}'"])
        if self.record_failed_num or setting.RECORD_FAILED_NUM:
            cmd.extend(["--record_failed_num", f"{self.record_failed_num or setting.RECORD_FAILED_NUM}"])
        if self.pytest_opt:
            cmd.extend([i.strip() for i in self.pytest_opt])

        if self.start_case:
            cmd.extend(["--start-case", f"{self.start_case}"])
        if self.interrupt_continue:
            cmd.extend(["--interrupt-continue"])
        if self.order_execution:
            cmd.extend(["--order-execution", f"{self.order_execution}"])

        cmd.extend([
            f"--reruns={self.reruns or setting.RERUNS}",
            f"--timeout={setting.TIMEOUT}",
        ])

        if self.setup_plan:
            cmd.append("--setup-plan")
        else:
            cmd.extend([
                f"--alluredir={self.allure_data_path}",
                "--clean-alluredir",
                "-s",
                "--no-header",
            ])

        return cmd

    def job_start_driver(self):
        from nocmd import Cmd
        if self.job_start:
            Cmd.run(self.job_start, timeout=3600)
        for file in os.listdir(self.rootdir):
            if file == "job_start.py":
                Cmd.run(f"cd {self.rootdir} && {sys.executable} {file}", timeout=600)
            if file == "job_start.sh":
                Cmd.run(f"cd {self.rootdir} && /bin/bash {file}", timeout=600)

    def job_end_driver(self):
        from nocmd import Cmd
        if self.job_end:
            Cmd.run(self.job_end, timeout=3600)
        for file in os.listdir(self.rootdir):
            if file == "job_end.py":
                Cmd.run(f"cd {self.rootdir} && {sys.executable} {file}", timeout=600)
            if file == "job_end.sh":
                Cmd.run(f"cd {self.rootdir} && /bin/bash {file}", timeout=600)

    def run(self):
        if not self.setup_plan:
            self.job_start_driver()
        print(" ".join(self.generate_cmd()))
        if self.workdir:
            if os.path.exists(self.workdir):
                os.chdir(self.workdir)
            else:
                raise FileNotFoundError(f"workdir not found: {self.workdir}")

        if self.start_case is not None and self.interrupt_continue:
            raise FileNotFoundError("parameter mutual exclusion: --start-case/--interrupt-continue")

        if self.order_execution is not None and self.interrupt_continue:
            raise FileNotFoundError("parameter mutual exclusion: --order-execution/--interrupt-continue")

        if self.order_execution is not None and self.order_execution not in ("asc", "desc"):
            raise ValueError("order-execution must be 'asc' or 'desc'")

        pytest.main(
            [i.strip("'") for i in self.generate_cmd()[1:]]
        )
        if self.setup_plan:
            return
        self.job_end_driver()
        self.gen_html()

    def gen_html(self):
        os.makedirs(self.allure_html_path, exist_ok=True)
        try:
            from youqu_html import YouQuHtml
            YouQuHtml.gen(str(self.allure_data_path), str(self.allure_html_path), clean=True)
        except ImportError:
            try:
                from youqu_html_rpc import YouQuHtmlRpc
                from youqu_html_rpc.config import config as html_rpc_config
                html_rpc_config.SERVER_IP = setting.REPORT_SERVER_IP
                YouQuHtmlRpc.environment(self.allure_data_path)
                YouQuHtmlRpc.gen_rpc(
                    self.allure_data_path,
                    self.allure_html_path,
                    setting.HOST_IP,
                    setting.REPORT_BASE_PATH,
                    self.rootdir.name
                )
            except ImportError:
                logger.info("Only JSON report, try: pip3 install youqu-html-rpc")
            except EnvironmentError:
                logger.info('You need to config the report server: setting.REPORT_SERVER_IP = "127.0.0.1/127.0.0.2"')


if __name__ == "__main__":
    Run().run()