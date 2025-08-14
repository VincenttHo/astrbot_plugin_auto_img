import aiohttp
from datetime import datetime
from astrbot.api.all import *
import asyncio
import json
from astrbot.api.message_components import Node


def is_time_between(start_time_str: str, end_time_str: str) -> bool:
    """
    判断当前时间是否在给定的时间段内（HH:mm格式）
    :param start_time_str: 开始时间字符串（HH:mm格式）
    :param end_time_str: 结束时间字符串（HH:mm格式）
    :return bool
    """
    try:
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
    except ValueError:
        print("错误：时间格式不正确，请使用 HH:mm 格式。")
        return False
    now_time = datetime.now().time()
    if start_time <= end_time:
        # 不跨天的情况
        # 当前时间必须大于等于开始时间，并且小于等于结束时间
        return start_time <= now_time <= end_time
    else:
        # 跨天的情况
        # 当前时间必须大于等于开始时间，或者小于等于结束时间
        return now_time >= start_time or now_time <= end_time

@register(
    "astrbot_plugin_auto_img",
    "VincenttHo",
    "自动发图插件,让你的bot定时给群或私聊发送图片",
    "1.0.0",
    "https://github.com/VincenttHo/astrbot_plugin_auto_img",
)
class PluginAutoImg(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.context = context

        # 获取配置
        self.send_forward = self.config.get("send_forward")
        self.image_size = self.config.get("image_size")
        self.schedule = self.config.get("schedule")
        self.bot_qq = self.config.get("bot_qq")
        exclude_time = config.get("exclude_time")
        self.exclude_start_time = exclude_time.get("start_time")
        self.exclude_end_time = exclude_time.get("end_time")

        # 定义消息用户类型
        self.user_type = {"FRIEND":"FriendMessage", "GROUP":"GroupMessage"}

        # 创建定时任务
        self.auto_trigger_task = asyncio.create_task(self._auto_trigger_task())

    async def _auto_trigger_task(self):
        """ 定时任务 """
        init_time = datetime.now().timestamp()
        schedule_list = json.loads(self.schedule)
        for schedule in schedule_list:
            schedule["last_activity"] = init_time
        while True:
            if not is_time_between(self.exclude_start_time, self.exclude_end_time):
                try:
                    await self.execute(schedule_list)
                except Exception as e:
                    logger.error(f"执行定时任务失败，原因：{str(e)}")
            # 间隔10秒检查一次
            await asyncio.sleep(10)

    async def execute(self, schedule_list):
        """
        定时任务执行逻辑
        :param schedule_list: 定时任务配置数组
        """
        for schedule in schedule_list:
            id = schedule.get("id")
            interval_sec = schedule.get("interval_sec")
            r18 = schedule.get("r18", 0)
            send_forward = schedule.get("send_forward", False)

            time_diff = datetime.now().timestamp() - schedule["last_activity"]
            if time_diff > interval_sec:
                type = self.user_type[schedule["type"]]
                unified_msg_origin = f"aiocqhttp:{type}:{id}"
                try:
                    await self.send_img(unified_msg_origin, r18, send_forward)
                    schedule["last_activity"] = datetime.now().timestamp()
                except Exception as e:
                    logger.error(f"定时任务发送{unified_msg_origin}失败，原因：{str(e)}")
                    pass
                # 5秒后再调用下一个
                await asyncio.sleep(5)


    async def send_img(self, unified_msg_origin, r18: str, send_forward):
        """
        发送图片
        :param unified_msg_origin: 发送目标用户
        :param r18: 是否发送r18图片
        :param send_forward: 是否用转发格式发送
        """
        lolicon_api = 'https://api.lolicon.app/setu/v2'
        async with aiohttp.ClientSession() as session:
            data = {
                "size": self.image_size,
                "excludeAI": True,
                "r18": r18
            }


            async with session.post(
                    lolicon_api,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    response.raise_for_status()
                    resp = await response.json()

                    img_info = resp["data"]
                    if not img_info:
                        logger.info("无返回")
                        return

                    img_url = resp["data"][0]["urls"][self.image_size]
                    img_title = resp["data"][0]["title"]
                    img_author = resp["data"][0]["author"]
                    img_pid = resp["data"][0]["pid"]
                    img_tags = resp["data"][0]["tags"]

                    if send_forward:
                        chain = MessageChain([Node(
                            uin=self.bot_qq,
                            name="AutoImg",
                            content=[
                                Image.fromURL(img_url),
                                Plain(
                                    f"标题：{img_title}\n作者：{img_author}\nPID：{img_pid}\n标签：{' '.join(f'#{tag}' for tag in (img_tags or []))}"
                                ),
                            ],
                        )])
                    else:
                        chain = MessageChain().url_image(img_url).message(
                            f"标题：{img_title}\n作者：{img_author}\nPID：{img_pid}\n标签：{' '.join(f'#{tag}' for tag in (img_tags or []))}")



                    # 使用 asyncio.wait_for 添加超时控制
                    # 设置90秒超时
                    timeout_sec = 90
                    try:
                        await asyncio.wait_for(
                            self.context.send_message(unified_msg_origin, chain),
                            timeout = timeout_sec
                        )
                    except asyncio.TimeoutError:
                        # 抛出超时消息
                        raise Exception(f"发送消息给 {unified_msg_origin} 超过时间：{timeout_sec}秒，已跳过。")
                    return

    def shutdown(self):
        self.auto_trigger_task.cancel()
        logger.info("定时触发任务已取消")

    def __del__(self):
        self.shutdown()

    def terminate(self):
        self.shutdown()