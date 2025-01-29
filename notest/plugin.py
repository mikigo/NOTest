import json
import os
import re
import copy
import shutil
import getpass
from datetime import datetime
from os.path import exists

from _pytest.mark import Mark
from funnylog2 import logger

from youqu3 import setting
from youqu3 import skipif

FLAG_FEEL = "=" * 10


def sort_items_by_key(items, order="asc"):
    """
    对用例列表进行升序排列
    :param items: 用例列表
    :param order: asc/desc用例执行顺序
    :return: 排序后用例列表
    """

    def __get_case_id_and_count(item, _order=order):
        match = re.finditer(r'(\d+)', item.name)
        num = 0
        if match:
            num_list = []
            for i in match:
                num_list.append(i.group())
                num_str = ''.join(map(str, num_list))
                num = int(num_str)

        if match:
            if _order == "asc":
                return int(num)
            if _order == "desc":
                return -int(num)

    items.sort(key=__get_case_id_and_count)


def section_items_by_case_function(items, case_function, index_offset=None):
    """
    指定用例开始位置
    :param items: 用例列表
    :param case_function: 用例函数名称
    :param index_offset: id 偏移量
    :return: 修改后用例列表
    """
    index_to_remove = None
    index_offset = index_offset if index_offset is not None else 0
    for index, item in enumerate(items):
        if f"{case_function}>" in str(item):
            index_to_remove = index + index_offset
            break

    if index_to_remove is not None:
        items[:index_to_remove] = []
    else:
        raise ValueError(f"用例列表中未发现：{case_function}")


def add_mark(item, name: str = "", args: tuple = (), kwargs: dict = None):
    item.own_markers.append(Mark(name=name, args=args, kwargs=kwargs))


def walk_apps(walk_dir):
    no_youqu_mark = {}
    csv_path_dict = {}
    for root, _, files in os.walk(walk_dir):
        if "NOMARKMANAGE" in files and not no_youqu_mark.get(root):
            no_youqu_mark[root] = True
            continue
        for file in files:
            if file.endswith(".csv") and file != "case_list.csv":
                csv_path_dict[os.path.splitext(file)[0]] = f"{root}/{file}"
    return csv_path_dict, no_youqu_mark


def pytest_addoption(parser):
    parser.addoption("--noskip", action="store", default="", help="skip-xxx标签不生效")
    parser.addoption("--ifixed", action="store", default="", help="fixed-xxx标签不生效")
    parser.addoption("--start-case", action="store", default="", help="指定执行用例开始位置")
    parser.addoption("--interrupt-continue", action="store_true", default="", help="执行中断续跑")
    parser.addoption("--order-execution", action="store", default="", help="指定用例编号执行顺序")


def pytest_sessionstart(session):
    logger("DEBUG")
    session.config.option.last_json_report_path = f"{session.fspath}/report/json/last_result.json"
    last_json_report = session.config.option.last_json_report_path
    case_order = session.config.getoption("--order-execution") or "pytest"
    start_case = session.config.getoption("--start-case") if session.config.getoption("--start-case") else "None"
    has_interrupt_continue = bool(session.config.getoption("--interrupt-continue"))

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_data = {
        "user": getpass.getuser(),
        "ip": setting.HOST_IP ,
        "execution_order": case_order,
        "interrupt_continue": has_interrupt_continue,
        "start_case": start_case,
        "py_total_passed_failed_skipped": "",
        "fun_total_passed_failed_skipped": "",
        "start_time": start_time,
        "end_time": "",
        "test_cases": {}
    }

    os.makedirs(os.path.dirname(last_json_report), exist_ok=True)
    if has_interrupt_continue:
        if not exists(last_json_report):
            raise ValueError("中断续跑模式下，未找到上次执行结果日志文件，请检查！")
    else:
        with open(last_json_report, 'w', encoding="utf-8") as f:
            json.dump(log_data, f, indent=4)


def pytest_report_teststatus(report, config):
    last_json_report = config.option.last_json_report_path
    case_py_path = report.nodeid.split('::')[0]
    case_py = os.path.basename(case_py_path)

    case_fun = report.nodeid.split('::')[-1]
    case_when = report.when
    case_outcome = report.outcome

    with open(last_json_report, "r", encoding="utf-8") as f:
        data = json.load(f)

    py_case_log_text = {
        "py_path": case_py_path,
        "py_outcome": "",
        "case_fun_set": {}
    }
    try:
        if case_py not in data["test_cases"]:
            data["test_cases"][case_py] = py_case_log_text

        if case_fun not in data["test_cases"][case_py]["case_fun_set"]:
            data["test_cases"][case_py]["case_fun_set"][case_fun] = {}

        data["test_cases"][case_py]["case_fun_set"][case_fun][case_when] = case_outcome
        if case_when == "setup" and case_outcome == "skipped":
            data["test_cases"][case_py]["case_fun_set"][case_fun]["call"] = "skipped"
        elif case_when == "setup" and case_outcome == "failed":
            data["test_cases"][case_py]["case_fun_set"][case_fun]["call"] = "failed"

        if case_when == "teardown":
            setup_result = data["test_cases"][case_py]["case_fun_set"][case_fun]["setup"]
            call_result = data["test_cases"][case_py]["case_fun_set"][case_fun]["call"]
            teardown_result = data["test_cases"][case_py]["case_fun_set"][case_fun]["teardown"]

            fun_outcome = "failed"
            if setup_result == "skipped":
                fun_outcome = "skipped"
            if setup_result == "passed" and call_result == "passed" and teardown_result == "passed":
                fun_outcome = "passed"
            if teardown_result == "failed":
                if call_result == "passed":
                    fun_outcome = "passed"
            data["test_cases"][case_py]["case_fun_set"][case_fun]["fun_outcome"] = fun_outcome

        with open(last_json_report, 'w', encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except KeyError:
        ...


def pytest_collection_modifyitems(session, config, items):
    last_json_report = session.config.option.last_json_report_path
    order_execution = config.getoption("--order-execution")
    if order_execution == "asc":
        sort_items_by_key(items, "asc")
    elif order_execution == "desc":
        sort_items_by_key(items, "desc")

    start_case = config.getoption("--start-case")
    if start_case:
        section_items_by_case_function(items, start_case)

    has_interrupt_continue = config.getoption("--interrupt-continue")
    if has_interrupt_continue:
        with open(last_json_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        order = data["execution_order"]
        if order == "desc" or order == "asc":
            sort_items_by_key(items, f"{order}")
        try:
            tmp_data = copy.deepcopy(data)
            last_case = tmp_data["test_cases"].popitem()[1]['case_fun_set'].popitem()[0]
        except KeyError:
            last_case = None
        if last_case:
            if f"<Function {last_case}>" == str(items[-1]):
                raise TypeError("最后一次测试未中断，无法进行续跑")
            else:
                section_items_by_case_function(items, last_case, 1)
        with open(last_json_report, "w", encoding="utf-8") as f:
            data["interrupt_continue"] = has_interrupt_continue
            json.dump(data, f, indent=4)

    csv_path_dict, no_youqu_mark = walk_apps(session.startdir)
    if not csv_path_dict:
        return
    containers = {}
    skip_index = fixed_index = removed_index = None
    for item in session.items[::-1]:
        item.name = item.name.encode("utf-8").decode("unicode_escape")
        item._nodeid = item.nodeid.encode("utf-8").decode("unicode_escape")

        if no_youqu_mark:
            continue_flag = False
            for app_abspath in no_youqu_mark:
                if app_abspath in item.fspath.strpath:
                    continue_flag = True
                    break
            if continue_flag:
                continue
        try:
            csv_name, _id = re.findall(r"test_(.*?)_(\d+)", item.name)[0]
            _case_name, _case_id = re.findall(r"test_(.*?)_(\d+)", item.fspath.purebasename)[0]
            if _id != _case_id:
                raise ValueError
            if _case_name != csv_name:
                raise FileNotFoundError
        except IndexError:
            skip_text = f"用例函数名称缺少用例id:[{item.nodeid}]"
            logger.error(skip_text)
            add_mark(item, setting.ConfStr.SKIP.value, (skip_text,), {})
        except ValueError:
            skip_text = f"用例py文件的id与用例函数的id不一致:[{item.nodeid}]"
            logger.error(skip_text)
            add_mark(item, setting.ConfStr.SKIP.value, (skip_text,), {})
        except FileNotFoundError:
            logger.error(f"用例py文件的名称与用例函数的名称不一致:[{item.nodeid}]")
            session.items.remove(item)
        else:
            csv_path = csv_path_dict.get(csv_name)
            if not csv_path:
                if "asan" not in csv_name:
                    logger.error(f"{csv_name}.csv 文件不存在!")
                continue

            if not containers.get(csv_path):
                with open(csv_path, "r", encoding="utf-8") as _f:
                    txt_list = _f.readlines()
                if not txt_list:
                    continue
                # 通过csv的表头找到对应的索引（排除ID列的索引）
                for index, title in enumerate(txt_list[0].strip().split(",")):
                    if title.strip() == setting.FixedCsvTitle.skip_reason.value:
                        skip_index = index - 1
                    elif title.strip() == setting.FixedCsvTitle.fixed.value:
                        fixed_index = index - 1
                    elif title.strip() == setting.FixedCsvTitle.removed.value:
                        removed_index = index - 1

                taglines = [txt.strip().split(",") for txt in txt_list[1:]]
                id_tags_dict = {f"{int(i[0]):0>3}": i[1:] for i in taglines if i[0]}

                containers[csv_path] = id_tags_dict
                containers[csv_path][setting.ConfStr.SKIP_INDEX.value] = skip_index
                containers[csv_path][setting.ConfStr.FIXED_INDEX.value] = fixed_index
                containers[csv_path][setting.ConfStr.REMOVED_INDEX.value] = removed_index
                skip_index = fixed_index = removed_index = None

            tags = containers.get(csv_path).get(_id)
            if tags:
                try:
                    if containers[csv_path][setting.ConfStr.REMOVED_INDEX.value] is not None and tags[
                        containers[csv_path][setting.ConfStr.REMOVED_INDEX.value]
                    ].strip('"').startswith(f"{setting.ConfStr.REMOVED.value}-"):
                        session.items.remove(item)
                        continue
                except IndexError as exc:
                    logger.error(
                        f"\ncsv_path:\t{csv_path}\ntags:\t{tags}\n"
                        f"error_tag_index:\t{containers[csv_path][setting.ConfStr.REMOVED_INDEX.value]}"
                    )
                    raise IndexError from exc
                for index, tag in enumerate(tags):
                    if tag:
                        tag = tag.strip('"')
                        # 先处理“跳过原因”列
                        if index == containers[csv_path][setting.ConfStr.SKIP_INDEX.value]:
                            # 标签是以 “skip-” 开头, noskip 用于解除所有的skip
                            if not session.config.option.noskip and tag.startswith(
                                    f"{setting.ConfStr.SKIP.value}-"
                            ):
                                # 标签以 “fixed-” 开头, ifixed表示ignore fixed, 用于忽略所有的fixed
                                # 1. 不给ifixed参数时，只要标记了fixed的用例，即使标记了skip-，也会执行；
                                # 2. 给ifixed 参数时(--ifixed yes)，fixed不生效，仅通过skip跳过用例；
                                try:
                                    if (
                                            not session.config.option.ifixed
                                            and containers[csv_path][setting.ConfStr.FIXED_INDEX.value]
                                            is not None
                                            and tags[containers[csv_path][setting.ConfStr.FIXED_INDEX.value]]
                                            .strip('"')
                                            .startswith(f"{setting.ConfStr.FIXED.value}-")
                                    ):
                                        continue
                                except IndexError:
                                    # 如果访问越界，说明这行没有fixed标签或者标签写错位置了，所以正常跳过
                                    pass
                                add_mark(item, setting.ConfStr.SKIP.value, (tag,), {})
                            elif (
                                    not session.config.option.noskip
                                    and f"{setting.ConfStr.SKIPIF.value}_" in tag
                            ):
                                tag_list = tag.split("&&")
                                for _tag in tag_list:
                                    skip_method, param = _tag.strip(" ").split("-", maxsplit=1)
                                    if hasattr(skipif, skip_method):
                                        skip_result = getattr(skipif, skip_method)(param)
                                        add_mark(
                                            item,
                                            setting.ConfStr.SKIPIF.value,
                                            (skip_result,),
                                            {"reason": _tag},
                                        )
                                    else:
                                        logger.error(
                                            f"未找到判断是否跳过的自定义方法 <{skip_method}>"
                                        )
                                        add_mark(
                                            item,
                                            setting.ConfStr.SKIP.value,
                                            (f"未找到判断是否跳过的自定义方法 <{skip_method}>",),
                                            {},
                                        )
                        else:  # 非跳过列
                            # 处理其他自定义标签
                            try:
                                mark_title = txt_list[0].strip().split(",")[index + 1]
                            except IndexError:
                                # 如果写了标签，但是没有对应的表头
                                mark_title = ""
                            add_mark(item, tag, (mark_title,), {})

            else:
                if session.config.option.allure_report_dir:
                    # 批量执行时，不执行没有ID的用例。
                    logger.error(f"<{item.name}> csv文件中未标记,强制跳过")
                    session.items.remove(item)

    print()  # 处理日志换行


def pytest_collection_finish(session):
    session.item_count = len(session.items)
    _items = session.items[:]
    is_skipped_case = False
    for item in _items[::-1]:
        for mark in item.own_markers:
            if mark.name == setting.ConfStr.SKIP.value:
                is_skipped_case = True
                try:
                    _items.remove(item)
                except ValueError:
                    ...
            elif mark.name == setting.ConfStr.SKIPIF.value and mark.args == (True,):
                is_skipped_case = True
                try:
                    _items.remove(item)
                except ValueError:
                    ...
    print(
        f"用例收集数量:\t{session.item_count} "
        f"{f'(剔除跳过: {len(_items)})' if is_skipped_case else ''}"
    )
    print(
        f"用例文件数量:\t{len(set([item.fspath for item in session.items]))} "
        f"{f'(剔除跳过: {len(set([item.fspath for item in _items]))})' if is_skipped_case else ''}"
    )


def pytest_runtest_setup(item):
    print()
    LN = "\n"
    current_item_count = f"[{item.session.items.index(item) + 1}/{item.session.item_count}] "
    try:
        current_item_percent = "{:.0f}%".format(
            int(item.session.items.index(item) + 1) / int(item.session.item_count) * 100
        )
    except:
        current_item_percent = ""
    try:
        rerun_text = f" | <重跑第{item.execution_count - 1}次>" if item.execution_count > 1 else ""
    except AttributeError:
        rerun_text = ""
    logger.info(
        f"{LN}{FLAG_FEEL} {item.function.__name__} | "
        f"{str(item.function.__doc__).replace(LN, '').replace('    ', '')}{rerun_text} "
        f"{FLAG_FEEL} {current_item_count} {current_item_percent}"
    )


def pytest_runtest_call(item):
    logger.info(f"{FLAG_FEEL} case body {FLAG_FEEL}")


def pytest_runtest_teardown(item):
    logger.info(f"{FLAG_FEEL} teardown {FLAG_FEEL}")


def pytest_sessionfinish(session):
    try:
        last_json_report = session.config.option.last_json_report_path
        with open(last_json_report, "r", encoding="utf-8") as f:
            data = json.load(f)

        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["end_time"] = end_time

        for _, case_py in data["test_cases"].items():
            outcomes = [fun_outcome for fun_results in case_py["case_fun_set"].values() for fun_outcome in fun_results.values()]
            if "failed" in outcomes:
                case_py["py_outcome"] = "failed"
            elif "failed" not in outcomes and "skipped" in outcomes:
                case_py["py_outcome"] = "skipped"
            elif len(set(outcomes)) == 1 and "passed" in set(outcomes):
                case_py["py_outcome"] = "passed"

        py_test_results = [py_result["py_outcome"] for py_result in data["test_cases"].values()]
        fun_test_results = [fun_result["fun_outcome"] for py in data["test_cases"].values() for fun_result in
                            py["case_fun_set"].values()]

        py_total_num = len(py_test_results)
        py_passed_num = py_test_results.count("passed")
        py_failed_num = py_test_results.count("failed")
        py_skipped_num = py_test_results.count("skipped")

        fun_total_num = len(fun_test_results)
        fun_passed_num = fun_test_results.count("passed")
        fun_failed_num = fun_test_results.count("failed")
        fun_skipped_num = fun_test_results.count("skipped")

        data["py_total_passed_failed_skipped"] = f"{py_total_num}/{py_passed_num}/{py_failed_num}/{py_skipped_num}"
        data["fun_total_passed_failed_skipped"] = f"{fun_total_num}/{fun_passed_num}/{fun_failed_num}/{fun_skipped_num}"

        with open(last_json_report, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        shutil.copy(last_json_report, f'{os.path.dirname(last_json_report)}/report_{setting.TIME_STRING}.json')
    except KeyError:
        ...