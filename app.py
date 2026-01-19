import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import time
from datetime import datetime

# --- 配置页面 ---
st.set_page_config(
    page_title="AI 视频提示词生成助手",
    page_icon="🎬",
    layout="wide"
)

# --- 状态初始化 ---
if "history" not in st.session_state:
    st.session_state["history"] = [] # 存储生成的历史记录对象

# --- 工具函数：Gemini 调用封装 ---
def call_gemini(api_key, system_instruction, user_content, media_files=None, chat_history=None):
    """
    调用 Gemini API 的通用函数
    :param api_key: 用户提供的 API Key
    :param system_instruction: 系统预设指令（定义工具角色）
    :param user_content: 用户的文本输入
    :param media_files: 图片或视频文件列表 [PIL.Image, File...]
    :param chat_history: 用于对话模式的历史上下文
    """
    if not api_key:
        return "请先在左侧侧边栏设置 Google API Key。"

    try:
        genai.configure(api_key=AIzaSyC3FET0LYqlWUDqNLXL8JiNS63qpyyXzm4)
        
        # 使用 Gemini 2.5 Pro
        model = genai.GenerativeModel(
            'gemini-2.5-pro',
            system_instruction=system_instruction
        )

        # 构建输入内容列表
        content_parts = [user_content]
        
        if media_files:
            for media in media_files:
                content_parts.append(media)

        # 如果是对话模式（修改/优化）
        if chat_history:
            chat = model.start_chat(history=chat_history)
            response = chat.send_message(content_parts)
            return response.text
        
        # 如果是首次生成
        response = model.generate_content(content_parts)
        return response.text

    except Exception as e:
        return f"API 调用出错: {str(e)}"

# --- 侧边栏：配置 ---
with st.sidebar:
    st.title("⚙️ 设置")
    api_key = st.text_input("请输入 Google Gemini API Key", type="password")
    st.markdown("---")
    st.info("提示：请确保 API Key 有权限访问 Gemini 1.5 Flash 模型。")

# --- 主页面 Tabs ---
tab1, tab2 = st.tabs(["🚀 立即生成", "📝 历史记录与优化"])

# ==========================================
# TAB 1: 生成工作台
# ==========================================
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
            st.markdown("**选择细分工具：**")
            tool_type = st.radio(
                "工具类型",
                ("1.图生视频 (Image-to-Video)",  "2.视频模仿 (Video Mimic)"),
                label_visibility="collapsed"
            )

        submit_btn = st.form_submit_button("✨ 点击立即生成", use_container_width=True)

    if submit_btn:
        # 1. 校验必填项
        if not product_name or not selling_points:
            st.error("请填写完整的商品名称和卖点！")
        elif not uploaded_image and tool_type != "3、视频模仿 (Video Mimic)":
             # 简化逻辑：图生视频通常需要图，但也允许纯文，这里按需求强制图
            st.error("请上传商品图片！")
        elif tool_type == "3、视频模仿 (Video Mimic)" and not uploaded_video:
            st.error("选择“视频模仿”工具必须上传参考视频！")
        else:
            # 2. 准备数据
            with st.spinner("正在分析素材并调用 Gemini 生成提示词..."):
                # 处理图片
                image_part = None
                if uploaded_image:
                    image_part = Image.open(uploaded_image)
                
                # 处理视频 (Gemini API 需先上传文件，这里简化为提示处理，实际生产需用 File API)
                # 注意：Streamlit 中直接传视频文件对象给 gemini python sdk 可能会受限
                # 这里的代码假设如果是视频模仿，我们主要依靠 prompt 描述参考视频的内容，或者假设 API key 支持直接流式上传
                # 为了代码稳定性，这里做简单的逻辑处理
                
                media_list = []
                if image_part:
                    media_list.append(image_part)
                
                # 构建 Prompt
                base_info = f"""
                **任务目标**：生成适合AI视频生成工具（如Runway, Pika, Sora）的英文提示词 (Prompts)。
                **投放市场**：{market}
                **商品名称**：{product_name}
                **商品卖点**：{selling_points}
                **营销文案**：{copywriting if copywriting else "无"}
                **生成数量**：{prompt_count} 条
                """

                system_instruction = ""
                user_prompt = ""

                if "图生视频" in tool_type:
                    system_instruction = "你是一位专业的AI视频提示词工程师。请根据用户提供的商品图片和卖点，生成描述画面运动、光影、镜头语言的英文提示词。重点在于展示产品细节和质感。"
                    user_prompt = f"{base_info}\n请基于上传的图片，生成 {prompt_count} 条高质量的 Image-to-Video 提示词，侧重于展现产品的高级感和卖点。"
                
                elif "图生 Clip" in tool_type:
                    system_instruction = "你是一位短视频营销专家。请生成简短、快节奏、吸睛的 Clip 提示词，适用于社交媒体（TikTok/Reels）的前3秒抓眼球。"
                    user_prompt = f"{base_info}\n请基于上传的图片，生成 {prompt_count} 条 Image-to-Clip 提示词，要求动作幅度大，视觉冲击力强。"
                
                elif "视频模仿" in tool_type:
                    system_instruction = "你是一位视频分镜分析师。请分析用户提供的参考视频（或对其描述）的镜头运镜、节奏和转场，并将这些风格应用到用户的商品上。"
                    # 注意：直接传视频给 Gemini 需要 File API 上传，这里为演示简化，仅基于图片+文本指令
                    # 实际生产中建议先使用 File API 上传视频获取 URI
                    user_prompt = f"{base_info}\n请参考(想象)参考视频的运镜风格，为这个商品生成 {prompt_count} 条模仿视频风格的提示词。确保保留参考视频的节奏感，但主角替换为本商品。"

                # 3. 调用 API
                result_text = call_gemini(api_key, system_instruction, user_prompt, media_list)

                # 4. 保存历史记录
                new_record = {
                    "id": str(int(time.time())),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "tool": tool_type,
                    "product": product_name,
                    "inputs": base_info,
                    "initial_result": result_text,
                    "chat_history": [ # 初始化对话历史，符合 Gemini 格式
                        {"role": "user", "parts": [user_prompt]},
                        {"role": "model", "parts": [result_text]}
                    ],
                    "system_instruction": system_instruction
                }
                st.session_state.history.insert(0, new_record) # 最新插在前面
                
                st.success("生成完成！请前往“历史记录与优化”标签页查看详情并进行微调。")
                st.markdown("### 本次生成预览：")
                st.write(result_text)

# ==========================================
# TAB 2: 历史记录与优化
# ==========================================
with tab2:
    st.header("📜 生成记录与优化")
    
    if not st.session_state.history:
        st.info("暂无生成记录，请去第一个标签页生成。")
    
    for record in st.session_state.history:
        with st.expander(f"[{record['timestamp']}] {record['product']} - {record['tool'].split(' ')[0]}"):
            
            col_a, col_b = st.columns([1, 2])
            
            with col_a:
                st.markdown("#### 原始需求")
                st.caption(record['inputs'])
                st.divider()
                st.markdown("#### 🛠️ 对话式修改")
                st.info("对结果不满意？在右侧直接与 AI 对话修改。")
            
            with col_b:
                # --- 聊天界面 ---
                chat_container = st.container(height=400)
                
                # 显示当前记录的对话历史
                for msg in record['chat_history']:
                    # 过滤掉初始的大段 prompt 显示，只显示后续交互，或者精简显示
                    if msg['role'] == 'user' and "任务目标" in msg['parts'][0]:
                        continue # 不显示初始的复杂 Prompt，保持界面清爽
                    
                    with chat_container.chat_message(msg['role']):
                        st.markdown(msg['parts'][0])

                # 显示初始结果（如果上面过滤了Model的回复，这里需要手动补一个初始结果的显示，或者直接利用chat流）
                # 为了简单清晰，我们直接显示完整的 chat history（除了第一条巨大的prompt）
                
                # 用户输入修改指令
                if prompt := st.chat_input(f"修改 {record['product']} 的提示词...", key=f"input_{record['id']}"):
                    # 1. 显示用户输入
                    with chat_container.chat_message("user"):
                        st.markdown(prompt)
                    
                    # 2. 更新本地历史
                    record['chat_history'].append({"role": "user", "parts": [prompt]})
                    
                    # 3. 调用 API 进行修改
                    with chat_container.chat_message("model"):
                        with st.spinner("AI 正在修改..."):
                            response_text = call_gemini(
                                api_key=api_key,
                                system_instruction=record['system_instruction'],
                                user_content=prompt,
                                media_files=None, # 修改阶段通常不需要重新传图，基于上下文即可
                                chat_history=record['chat_history'][:-1] # 传入之前的历史
                            )
                            st.markdown(response_text)
                    
                    # 4. 更新模型回复到历史
                    record['chat_history'].append({"role": "model", "parts": [response_text]})
                    # 强制刷新以保存状态 (Streamlit 特性)
                    st.rerun()
