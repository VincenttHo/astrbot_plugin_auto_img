import aiohttp
from datetime import datetime
from astrbot.api.all import *
import asyncio
import json
from astrbot.api.message_components import Node
import random
from astrbot.api.event.filter import command, command_group


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

def get_this_hour_start_time():
    """获取当前小时的开始时间"""
    this_hour_start_time_str = datetime.now().strftime("%Y-%m-%d %H:") + "00:00"
    return datetime.strptime(this_hour_start_time_str, "%Y-%m-%d %H:%M:%S")

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
        self.config = self.context.get_registered_star("astrbot_plugin_auto_img").config
        self.context = context

        # 获取配置
        self.send_forward = self.config.get("send_forward")
        self.image_size = self.config.get("image_size")
        self.schedule = self.config.get("schedule")
        self.bot_qq = self.config.get("bot_qq")
        exclude_time = self.config.get("exclude_time")
        self.exclude_start_time = exclude_time.get("start_time")
        self.exclude_end_time = exclude_time.get("end_time")
        self.send_img_messages = self.config.get("send_img_messages")

        # 定义消息用户类型
        self.user_type = {"FRIEND":"FriendMessage", "GROUP":"GroupMessage"}

        # 创建定时任务
        self.auto_trigger_task = asyncio.create_task(self._auto_trigger_task())

    async def _auto_trigger_task(self):
        """ 定时任务 """
        init_time = datetime.now().timestamp()
        schedule_list = json.loads(self.schedule)
        for schedule in schedule_list:
            schedule["last_activity"] = get_this_hour_start_time().timestamp()
            logger.info(f"[定时图片插件] 已加载定时配置：{schedule}")
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

        user_id = unified_msg_origin.split(":")[2]

        async with aiohttp.ClientSession() as session:
            data = {
                "size": self.image_size,
                "excludeAI": True,
                "r18": r18
            }
            tag = self.get_user_tags(user_id)
            if tag:
                data["tag"] = tag.split("&")

            logger.info(f"入参：{data}")

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
                        if self.send_img_messages:
                            idx = random.randint(0, len(self.send_img_messages)-1)
                            await self.context.send_message(unified_msg_origin, MessageChain().message(self.send_img_messages[idx]))
                    except asyncio.TimeoutError:
                        # 抛出超时消息
                        raise Exception(f"发送消息给 {unified_msg_origin} 超过时间：{timeout_sec}秒，已跳过。")
                    return

    @command_group("auto_img")
    async def auto_img(self):
        pass

    @auto_img.command("set_my_tags")
    async def custom_tags(self, event: AstrMessageEvent, tag: str):
        logger.info(f"接收到信息：{tag}")
        sender_id = event.get_group_id()
        if not sender_id:
            sender_id = event.get_sender_id()
        if not self.config.get("custom_tags"):
            self.config["custom_tags"] = {}
        self.config.get("custom_tags")[sender_id] = tag
        self.config.save_config(self.config)
        yield event.plain_result("成功设置！")

    @auto_img.command("my_tags")
    async def get_my_tags(self, event: AstrMessageEvent):
        sender_id = event.get_group_id()
        if not sender_id:
            sender_id = event.get_sender_id()
        yield event.plain_result("你的tag是：" + self.get_user_tags(sender_id))

    @auto_img.command("get")
    async def get_img(self, event: AstrMessageEvent):
        try:
            await self.send_img(event.unified_msg_origin, "2", True)
        except Exception as e:
            yield event.plain_result(f"发生错误：{str(e)}")

    @auto_img.command("help")
    async def help(self, event: AstrMessageEvent):
        help_message = "命令帮助：\n 1. /auto_img set_my_tags [标签设置] （标签设置可以设置多个，&表示and，|表示or。如：“JK|黑丝&雷姆|拉姆” 请不要带空格） \n2. /auto_img my_tags （我的标签设置） \n3. /auto_img get （根据当前设置获取一张图片）"
        yield event.plain_result(help_message)

    def get_user_tags(self, user_id):
        if not self.config.get("custom_tags"):
            self.config["custom_tags"] = {}
        return self.config.get("custom_tags").get(user_id, "")

    async def terminate(self):
        self.auto_trigger_task.cancel()
        logger.info("[定时图片插件] 定时触发任务已取消")