import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import streamlit as st
from PIL import Image

from google import genai
from google.genai import types

# =========================
# Streamlit page config
# =========================
st.set_page_config(
    page_title="AI 视频提示词生成助手",
    page_icon="🎬",
    layout="wide"
)

# =========================
# Read API key from Streamlit Cloud Secrets / env
# =========================
API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("AIzaSyC3FET0LYqlWUDqNLXL8JiNS63qpyyXzm4", ""))
if not API_KEY:
    st.error("缺少 GEMINI_API_KEY：请在 Streamlit Cloud -> Manage app -> Settings -> Secrets 中配置。")
    st.stop()

MODEL_NAME = "gemini-2.5-pro"
client = genai.Client(api_key=API_KEY)

# =========================
# Session state init
# =========================
if "history" not in st.session_state:
    st.session_state["history"] = []  # list of records


# =========================
# Gemini call helper
# =========================
def call_gemini(system_instruction: str, user_text: str, media_files: Optional[List[Image.Image]] = None) -> str:
    try:
        contents: List[Any] = [user_text]
        if media_files:
            contents.extend(media_files)

        cfg = types.GenerateContentConfig(
            system_instruction=system_instruction,
        )

        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=cfg
        )
        return resp.text or ""
    except Exception as e:
        return f"API 调用出错: {e}"


def build_base_info(market: str, product_name: str, selling_points: str, copywriting: str, prompt_count: int) -> str:
    return f"""
任务目标：生成适合 AI 视频生成工具（如 Runway, Pika, Sora）的英文提示词（Prompts）。
投放市场：{market}
商品名称：{product_name}
商品卖点：{selling_points}
营销文案：{copywriting if copywriting else "无"}
生成数量：{prompt_count} 条
""".strip()


def build_generation_prompt(tool_type: str, base_info: str, prompt_count: int) -> Dict[str, str]:
    if tool_type.startswith("图生视频"):
        system_instruction = (
            "你是一位专业的AI视频提示词工程师。"
            "请根据用户提供的商品图片和卖点，生成描述画面运动、光影、镜头语言的英文提示词。"
            "重点展示产品细节、质感和卖点，每条提示词都可直接用于图生视频模型。"
        )
        user_prompt = f"""{base_info}

请基于上传的商品图片，生成 {prompt_count} 条高质量 Image-to-Video 英文提示词。
每条提示词必须包含：
- 镜头景别（close-up/medium/wide）
- 运镜（push-in/dolly/pan/handheld）
- 光线与氛围（softbox/clean studio/warm/cool）
- 场景（studio/lifestyle/bathroom/desk）
- 动作变化（open/apply/press/massage/before-after）
- 时长建议（例如 4-6s）
- 风格标签（UGC / cinematic / ASMR / clean product）

输出格式要求：
- 仅输出编号列表 1..{prompt_count}
- 每条为一整段英文 prompt
"""
    else:
        system_instruction = (
            "你是一位视频分镜与广告创意分析师。"
            "请将参考视频的镜头语言/节奏/氛围风格迁移到该商品上，输出可直接用于生成视频的英文提示词。"
            "注意：当前未直接解析视频画面，请仍然按“模仿TikTok爆款广告节奏”的方式写出镜头与剪辑感。"
        )
        user_prompt = f"""{base_info}

请生成 {prompt_count} 条“视频模仿风格”的英文提示词（主角为该商品）：
要求：
- 快节奏剪辑感，强对比、强卖点呈现，适合 TikTok / Reels
- 至少包含：1条极致微距细节、1条使用过程/效果呈现、1条场景化展示
- 每条必须包含：景别、运镜、光线氛围、场景、动作变化、时长建议、风格标签

输出格式要求：
- 仅输出编号列表 1..{prompt_count}
- 每条为一整段英文 prompt
"""
    return {"system": system_instruction, "user": user_prompt}


def build_refine_prompt(record: Dict[str, Any], user_edit: str) -> str:
    # 只取最近几轮对话，避免上下文过长
    history_lines = []
    for m in record["chat_history"][-10:]:
        history_lines.append(f"{m['role'].upper()}: {m['text']}")
    history_block = "\n".join(history_lines)

    return f"""
你正在对一份“视频提示词生成结果”做二次修改。

【工具类型】{record["tool"]}
【原始需求】
{record["inputs"]}

【上一版生成结果】
{record["initial_result"]}

【对话上下文（最近）】
{history_block}

【用户这次修改要求】
{user_edit}

请输出：修改后的完整提示词版本（保持同样条数与编号）。
不要解释过程，直接给结果。
""".strip()


# =========================
# Sidebar (no key input)
# =========================
with st.sidebar:
    st.title("⚙️ 设置")
    st.caption("✅ API Key 已从 Streamlit Cloud Secrets/env 自动读取，无需页面输入")
    st.markdown(f"**当前模型：** `{MODEL_NAME}`")
    st.markdown("---")
    st.info("如需更换 Key：Manage app → Settings → Secrets → 修改 GEMINI_API_KEY")


# =========================
# UI Tabs
# =========================
tab1, tab2 = st.tabs(["🚀 立即生成", "📝 历史记录与优化"])

# -------------------------
# TAB 1: Generation
# -------------------------
with tab1:
    st.header("视频提示词生成工作流")

    with st.form("generation_form"):
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("1. 基础信息")
            market = st.selectbox("投放市场", ["美国 (US)", "英国 (UK)", "东南亚", "欧洲其他", "全球"], index=0)
            product_name = st.text_input("商品名称 (必填)", placeholder="例如：智能补光灯")
            selling_points = st.text_area("商品卖点 (必填)", placeholder="例如：三色温调节，超长续航，磁吸设计...")
            copywriting = st.text_area("文案 (选填)", placeholder="例如：Tiktok爆款...")
            prompt_count = st.slider("生成 Prompt 条数", 1, 5, 3)

        with col2:
            st.subheader("2. 附件与工具")
            uploaded_image = st.file_uploader("上传商品图片 (必选)", type=["jpg", "png", "jpeg"])
            uploaded_video = st.file_uploader("上传参考视频 (视频模仿必选)", type=["mp4", "mov"])

            st.markdown("---")
            tool_type = st.radio(
                "工具类型",
                ("图生视频 (Image-to-Video)", "视频模仿 (Video Mimic)"),
                label_visibility="collapsed"
            )

        submit_btn = st.form_submit_button("✨ 点击立即生成", use_container_width=True)

    if submit_btn:
        if not product_name.strip() or not selling_points.strip():
            st.error("请填写完整的商品名称和卖点！")
            st.stop()

        # 需求：商品图片必选
        if uploaded_image is None:
            st.error("请上传商品图片（必选）。")
            st.stop()

        # 需求：视频模仿视频必选
        if tool_type.startswith("视频模仿") and uploaded_video is None:
            st.error("选择“视频模仿”工具必须上传参考视频！")
            st.stop()

        with st.spinner("正在调用 Gemini 2.5 Pro 生成提示词..."):
            image_part = Image.open(uploaded_image).convert("RGB")

            base_info = build_base_info(market, product_name, selling_points, copywriting, prompt_count)
            prompts = build_generation_prompt(tool_type, base_info, prompt_count)

            # 当前：图生/模仿都只把“商品图”传给模型
            # 真正的视频理解需要把视频上传到 Gemini Files API，再用 URI 传入（后续我也能给你接）
            result_text = call_gemini(
                system_instruction=prompts["system"],
                user_text=prompts["user"],
                media_files=[image_part],
            )

            record = {
                "id": str(int(time.time() * 1000)),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tool": tool_type,
                "product": product_name,
                "inputs": base_info,
                "initial_prompt": prompts["user"],
                "initial_result": result_text,
                "system_instruction": prompts["system"],
                "chat_history": [
                    {"role": "user", "text": prompts["user"]},
                    {"role": "assistant", "text": result_text},
                ],
            }

            st.session_state.history.insert(0, record)

        st.success("生成完成！请前往“历史记录与优化”标签页查看详情并进行微调。")
        st.markdown("### 本次生成预览：")
        st.write(result_text)

# -------------------------
# TAB 2: History + refine
# -------------------------
with tab2:
    st.header("📜 生成记录与优化")

    if not st.session_state.history:
        st.info("暂无生成记录，请去第一个标签页生成。")
    else:
        for idx, record in enumerate(st.session_state.history):
            title = f"[{record['timestamp']}] {record['product']} - {record['tool'].split(' ')[0]}"

            with st.expander(title, expanded=(idx == 0)):
                col_a, col_b = st.columns([1, 2])

                with col_a:
                    st.markdown("#### 原始需求")
                    st.caption(record["inputs"])
                    st.divider()
                    st.markdown("#### 🛠️ 对话式修改")
                    st.info("输入修改要求并发送，例如：更ASMR、更快节奏、突出卖点、加微距特写、加入对比镜头等。")

                with col_b:
                    # show chat
                    for msg in record["chat_history"]:
                        with st.chat_message(msg["role"]):
                            st.markdown(msg["text"])

                    user_edit = st.text_input("输入你的修改要求", key=f"edit_{record['id']}")
                    send = st.button("发送修改", key=f"send_{record['id']}")

                    if send:
                        if not user_edit.strip():
                            st.warning("先输入修改要求再发送～")
                            st.stop()

                        record["chat_history"].append({"role": "user", "text": user_edit})
                        refine_prompt = build_refine_prompt(record, user_edit)

                        with st.spinner("AI 正在修改..."):
                            response_text = call_gemini(
                                system_instruction=record["system_instruction"],
                                user_text=refine_prompt,
                                media_files=None
                            )

                        record["chat_history"].append({"role": "assistant", "text": response_text})
                        record["initial_result"] = response_text

                        st.session_state.history[idx] = record
                        st.rerun()
