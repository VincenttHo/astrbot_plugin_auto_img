import aiohttp
from datetime import datetime
from astrbot.api.all import *
import asyncio
import json
from astrbot.api.message_components import Node
import random
from astrbot.api.event.filter import command, command_group
from typing import Optional
import concurrent.futures


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
    "1.1.0",
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
        self.schedule_json_config = self.config.get("schedule")
        self.schedule_list = json.loads(self.schedule_json_config)
        self.bot_qq = self.config.get("bot_qq")
        exclude_time = self.config.get("exclude_time")
        self.exclude_start_time = exclude_time.get("start_time")
        self.exclude_end_time = exclude_time.get("end_time")
        self.send_img_messages = self.config.get("send_img_messages")
        self.proxy = self.config.get("proxy")

        # 定义消息用户类型
        self.user_type = {"FRIEND":"FriendMessage", "GROUP":"GroupMessage"}

        # 创建定时任务
        self.auto_trigger_task = asyncio.create_task(self._auto_trigger_task())

    async def _auto_trigger_task(self):
        """ 定时任务 """
        for schedule in self.schedule_list:
            schedule["last_activity"] = get_this_hour_start_time().timestamp()
            logger.info(f"[定时图片插件] 已加载定时配置：{schedule}")
        while True:
            if not is_time_between(self.exclude_start_time, self.exclude_end_time):
                try:
                    await self.execute()
                except Exception as e:
                    logger.error(f"执行定时任务失败，原因：{str(e)}")
            # 间隔10秒检查一次
            await asyncio.sleep(10)

    async def execute(self):
        """
        定时任务执行逻辑
        :param schedule_list: 定时任务配置数组
        """
        for schedule in self.schedule_list:
            id = schedule.get("id")
            interval_sec = schedule.get("interval_sec")

            time_diff = datetime.now().timestamp() - schedule["last_activity"]
            if time_diff > interval_sec:
                type = self.user_type[schedule["type"]]
                unified_msg_origin = f"default:{type}:{id}"
                try:
                    await self.send_img(unified_msg_origin, schedule)
                    schedule["last_activity"] = datetime.now().timestamp()
                except Exception as e:
                    logger.error(f"定时任务发送{unified_msg_origin}失败，原因：{str(e)}")
                    pass
                # 5秒后再调用下一个
                await asyncio.sleep(5)


    async def send_img(self, unified_msg_origin, schedule):
        """
        发送图片
        :param unified_msg_origin: 发送目标用户
        :param schedule: 调度配置
        """
        # 从schedule配置中获取API类型，默认使用lolicon
        api_type = schedule.get("api_type", "lolicon")
        
        # 根据配置选择API
        if api_type == "alcy":
            await self.send_img_alcy(unified_msg_origin, schedule)
        else:
            await self.send_img_lolicon(unified_msg_origin, schedule)

    async def send_img_alcy(self, unified_msg_origin, schedule):
        """
        使用alcy API发送图片
        :param unified_msg_origin: 发送目标用户
        :param schedule: 调度配置
        """
        alcy_api = 'https://t.alcy.cc/json'

        send_forward = schedule.get("send_forward", False)
        category = schedule.get("category", "pc")  # 图片分类
        count = schedule.get("count", 1)  # 获取数量

        async with aiohttp.ClientSession() as session:
            # 构建请求URL
            url = f"{alcy_api}?{category}={count}"
            logger.info(f"请求URL：{url}")

            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    response.raise_for_status()
                    resp = await response.json()

                    if resp.get("code") != 200:
                        logger.error(f"API返回错误：{resp}")
                        return

                    data = resp.get("data")
                    if not data:
                        logger.info("无返回数据")
                        return

                    # 处理单条或多条数据
                    if isinstance(data, dict):
                        # 单条数据
                        img_url = data.get("link")
                        await self._send_single_image(unified_msg_origin, img_url, "", send_forward)
                    elif isinstance(data, list):
                        # 多条数据
                        for item in data:
                            img_url = item.get("link")
                            await self._send_single_image(unified_msg_origin, img_url, "", send_forward)
                            await asyncio.sleep(2)  # 多张图片之间间隔2秒

                    # 发送附加消息
                    if self.send_img_messages:
                        idx = random.randint(0, len(self.send_img_messages)-1)
                        await self.context.send_message(unified_msg_origin, MessageChain().message(self.send_img_messages[idx]))

            except Exception as e:
                logger.error(f"alcy API调用失败：{str(e)}")
                raise

    async def send_img_lolicon(self, unified_msg_origin, schedule):
        """
        使用lolicon API发送图片（原有逻辑）
        :param unified_msg_origin: 发送目标用户
        :param schedule: 调度配置
        """
        lolicon_api = 'https://api.lolicon.app/setu/v2'

        send_forward = schedule.get("send_forward", False)
        detail_mode = schedule.get("detail_mode")
        show_detail = schedule.get("show_detail", True)
        call_ai = schedule.get("call_ai", False)
        r18 = schedule.get("r18", 0)
        exclude_tags = schedule.get("exclude_tags", [])
        logger.info(f"排除tags:{exclude_tags}")

        user_id = unified_msg_origin.split(":")[2]

        async with aiohttp.ClientSession() as session:
            data = {
                "size": self.image_size,
                "excludeAI": True,
                "r18": r18,
                "proxy": self.proxy
            }
            tag = self.get_user_tags(user_id)
            if tag:
                data["tag"] = tag.split("&")

            logger.info(f"入参：{data}")

            # 循环调用接口，直到获取到不包含 exclude_tags 的图片
            max_retries = 10  # 设置最大重试次数，避免无限循环
            retry_count = 0
            
            while retry_count < max_retries:
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

                        img_tags = resp["data"][0]["tags"]
                        # 检查是否包含排除的标签（模糊匹配）
                        has_excluded_tag = any(
                            any(excluded_tag in img_tag for img_tag in img_tags)
                            for excluded_tag in exclude_tags
                        )
                        
                        if has_excluded_tag:
                            retry_count += 1
                            logger.info(f"图片包含排除标签，重新获取... (第 {retry_count} 次)")
                            continue
                        
                        # 如果没有排除标签，继续处理
                        img_url = resp["data"][0]["urls"][self.image_size]
                        img_title = resp["data"][0]["title"]
                        img_author = resp["data"][0]["author"]
                        img_pid = resp["data"][0]["pid"]

                        full_image_info = f"标题：{img_title}\n作者：{img_author}\nPID：{img_pid}\n标签：{' '.join(f'#{tag}' for tag in (img_tags or []))}"
                        brief_image_info = f"标题：{img_title}\n作者：{img_author}\nPID：{img_pid}"
                        show_image_detail = self._build_lolicon_detail_text(
                            detail_mode,
                            show_detail,
                            full_image_info,
                            brief_image_info,
                        )

                        if call_ai and not self._is_brief_detail_mode(detail_mode):
                            try:
                                ai_response = await self.chat_with_ai(full_image_info)
                                if show_image_detail == "":
                                    show_image_detail = ai_response
                                else:
                                    show_image_detail = show_image_detail + "\n" + ai_response
                            except Exception as e:
                                show_image_detail = show_image_detail


                        await self._send_single_image(unified_msg_origin, img_url, show_image_detail, send_forward)

                        # 发送附加消息
                        if self.send_img_messages:
                            idx = random.randint(0, len(self.send_img_messages)-1)
                            await self.context.send_message(unified_msg_origin, MessageChain().message(self.send_img_messages[idx]))
                        return
            
            # 如果达到最大重试次数仍未找到合适的图片
            logger.warning(f"已重试 {max_retries} 次，仍未找到不包含排除标签的图片")
            return

    def _build_lolicon_detail_text(self, detail_mode, show_detail, full_image_info, brief_image_info):
        """
        根据配置生成lolicon图片信息文本。
        detail_mode优先级高于旧的show_detail配置，以保持向后兼容。
        """
        if detail_mode is None:
            return full_image_info if show_detail else ""

        mode = str(detail_mode).lower()
        if mode in ("brief", "simple"):
            return brief_image_info
        if mode in ("none", "off", "false"):
            return ""
        return full_image_info

    def _is_brief_detail_mode(self, detail_mode):
        return str(detail_mode).lower() in ("brief", "simple")

    async def _send_single_image(self, unified_msg_origin, img_url, detail_text, send_forward):
        """
        发送单张图片的通用方法
        :param unified_msg_origin: 发送目标
        :param img_url: 图片URL
        :param detail_text: 详细信息文本
        :param send_forward: 是否使用转发格式
        """
        if send_forward:
            chain = MessageChain([Node(
                uin=self.bot_qq,
                name="AutoImg",
                content=[
                    Image.fromURL(img_url),
                    Plain(detail_text) if detail_text else Plain(""),
                ],
            )])
        else:
            if detail_text:
                chain = MessageChain().url_image(img_url).message(detail_text)
            else:
                chain = MessageChain().url_image(img_url)

        # 使用 asyncio.wait_for 添加超时控制
        timeout_sec = 90
        try:
            await asyncio.wait_for(
                self.context.send_message(unified_msg_origin, chain),
                timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            raise Exception(f"发送消息给 {unified_msg_origin} 超过时间：{timeout_sec}秒，已跳过。")
        except Exception as e:
            error_msg = f"发送消息给 {unified_msg_origin} 时发生未知错误: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            raise

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
            logger.info(f"消息发送串：{event.unified_msg_origin}")
            sender_id = event.get_group_id()
            if not sender_id:
                sender_id = event.get_sender_id()
            for schedule in self.schedule_list:
                if schedule.get("id", "") == sender_id:
                    await self.send_img(event.unified_msg_origin, schedule)
                    break
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

    async def chat_with_ai(self, messages: str) -> Optional[str]:
        """调用AI接口进行聊天"""
        try:
            # 在线程池中运行同步函数
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result, is_key_error = await loop.run_in_executor(
                    executor,
                    lambda: self._sync_chat_with_ai(messages)
                )

            if result:
                return result
            else:
                # 非密钥错误，直接返回失败
                return "抱歉，AI服务暂时不可用，请稍后再试"

        except Exception as e:
            logger.error(f"ai调用: 调用AI接口时发生错误: {str(e)}")

    def _sync_chat_with_ai(self, messages: str) -> tuple[Optional[str], bool]:
        """同步版本的AI聊天函数，支持完整的消息历史

        Returns:
            tuple: (response_content, is_key_error)
            - response_content: AI的回复内容，失败时为None
        """
        import requests
        import json

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer ff086c5a-6c3b-48f5-8e14-c08d188baae3"
        }

        system_prompt = "请根据用户提供给你的文字信息，根据标题和标签，用中文说出一句符合情景的淫语。要求：淫语尺度要大。使用第一人称扮演情景里的角色。"

        request_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": messages}]

        request_body = {
            "model": "nalang-turbo-v23",
            "messages": request_messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 800,
            "top_p": 0.35,
            "repetition_penalty": 1.05
        }

        all_content_parts = []

        try:
            with requests.post("https://www.gpt4novel.com/api/xiaoshuoai/ext/v1/chat/completions", headers=headers, json=request_body, stream=True) as response:
                # 检查HTTP状态码
                if response.status_code == 401:
                    logger.warning(f"ai调用: API密钥认证失败 (401)")
                    return None, True
                elif response.status_code == 429:
                    logger.warning(f"ai调用: API使用次数超限 (429)")
                    return None, True
                elif response.status_code == 403:
                    logger.warning(f"ai调用: API访问被拒绝 (403)")
                    return None, True

                response.raise_for_status()

                for line_bytes in response.iter_lines():
                    if line_bytes:
                        decoded_line = line_bytes.decode('utf-8')

                        if decoded_line.startswith('data: '):
                            json_data_str = decoded_line[len('data: '):].strip()

                            if not json_data_str:
                                continue

                            if json_data_str == "[DONE]":
                                break

                            try:
                                json_data = json.loads(json_data_str)

                                # 检查是否有错误信息
                                if "error" in json_data:
                                    error_info = json_data["error"]
                                    error_code = error_info.get("code", "")
                                    error_message = error_info.get("message", "")

                                    # 检查是否是密钥相关错误
                                    if any(keyword in error_message.lower() for keyword in
                                           ["quota", "limit", "exceeded", "insufficient", "balance", "credit"]):
                                        logger.warning(f"ai调用: API密钥使用限制错误: {error_message}")
                                        return None, True
                                    elif "invalid" in error_message.lower() and "key" in error_message.lower():
                                        logger.warning(f"ai调用: API密钥无效错误: {error_message}")
                                        return None, True
                                    else:
                                        logger.error(f"ai调用: API返回错误: {error_message}")
                                        return None, True

                                if json_data.get("completed"):
                                    break

                                choices = json_data.get("choices")
                                if choices and len(choices) > 0:
                                    delta = choices[0].get("delta")
                                    if delta and delta.get("content"):
                                        content_piece = delta["content"]
                                        all_content_parts.append(content_piece)

                            except json.JSONDecodeError:
                                if json_data_str.strip():
                                    logger.warning(f"ai调用: 解析JSON时出错: '{json_data_str}'")

            if all_content_parts:
                return "".join(all_content_parts), False
            else:
                return None, False

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            # 检查是否是密钥相关的网络错误
            if any(keyword in error_msg.lower() for keyword in ["401", "403", "429", "unauthorized", "forbidden"]):
                logger.error(f"ai调用: API密钥相关的请求错误: {error_msg}")
                return None, True
            else:
                logger.error(f"ai调用: 网络请求错误: {error_msg}")
                return None, False
        except Exception as e:
            logger.error(f"ai调用: 发生未知错误: {str(e)}")
            return None, False

    async def terminate(self):
        self.auto_trigger_task.cancel()
        logger.info("[定时图片插件] 定时触发任务已取消")
