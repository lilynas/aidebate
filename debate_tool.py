import os
import openai
import configparser
import datetime
import re
import json

# --- 1. 配置加载 (已修复编码问题) ---
def load_config():
    """从 config.ini 加载配置"""
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        raise FileNotFoundError("错误：未找到 config.ini 配置文件。请根据说明创建该文件。")
    
    # 明确指定使用 utf-8 编码读取配置文件
    config.read('config.ini', encoding='utf-8')
    
    return {
        'base_url': config['openai']['base_url'],
        'api_key': config['openai']['api_key'],
        'model_name': config['openai']['model_name'],
        'judge_model_name': config['openai']['judge_model_name']
    }

# --- 2. AI 模型交互 ---
def get_ai_response(client, model_name, messages):
    """获取 AI 模型的响应"""
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7, # 保持一定的创造性
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[!] 调用API时发生错误: {e}")
        # 在真实应用中可能需要更复杂的错误处理，例如重试
        return "抱歉，我在思考时遇到了一个问题，无法继续发言。"

# --- 3. 辩论流程控制 ---
def run_debate(client, settings):
    """运行完整的辩论流程"""
    topic = settings['topic']
    max_rounds = settings['max_rounds']
    pro_role = settings['pro_role']
    con_role = settings['con_role']
    pro_system_prompt = settings['pro_system_prompt']
    con_system_prompt = settings['con_system_prompt']

    # 初始化对话历史
    debate_history = []
    
    # 定义AI角色
    judge_model = settings['judge_model_name']
    debater_model = settings['model_name']

    # --- 开场白 ---
    print("==================== 辩论开始 ====================")
    judge_intro_prompt = f"""你是一位辩论比赛的裁判。你的任务是主持一场关于“{topic}”的辩论。
请先说一段开场白，介绍辩论主题，以及正方（角色：{pro_role}）和反方（角色：{con_role}）。
然后，宣布辩论开始，并邀请正方首先发言。
你的发言需要保持中立、客观，并营造一种正式而专业的辩论氛围。"""
    
    judge_messages = [{"role": "system", "content": judge_intro_prompt}]
    intro = get_ai_response(client, judge_model, judge_messages)
    print(f"\n--- 裁判 ---\n{intro}\n")
    debate_history.append({"role": "裁判", "content": intro})
    
    # 更新裁判的记忆，让它知道自己已经说完了开场白
    judge_messages.append({"role": "assistant", "content": intro})

    # --- 辩论循环 ---
    for i in range(max_rounds):
        round_num = i + 1
        print(f"-------------------- 第 {round_num} 轮 --------------------")

        # == 正方发言 ==
        pro_prompt = f"""你是正方辩手，你的角色是：{pro_role}。
辩论主题：“{topic}”。你的核心立场是支持这个主题。
这是你之前的发言，作为参考：{[msg['content'] for msg in debate_history if msg['role'] == '正方']}
这是你的对手（反方）的发言：{[msg['content'] for msg in debate_history if msg['role'] == '反方']}
现在轮到你发言。请根据你角色的立场，有逻辑地陈述你的观点。如果这是第一轮，请进行开篇立论。如果是后续轮次，请在陈述新观点的同时，反驳反方上一轮的观点。
请直接开始你的发言。"""
        pro_messages = [{"role": "system", "content": pro_system_prompt or pro_prompt}]
        # 将相关历史加入上下文，但为了节省token，可以只加入最近几轮
        pro_messages.extend([{"role": "user" if m["role"] == "反方" else "assistant", "content": m["content"]} for m in debate_history if m["role"] in ["正方", "反方"]])
        
        pro_statement = get_ai_response(client, debater_model, pro_messages)
        print(f"\n--- 正方 (角色: {pro_role}) ---\n{pro_statement}\n")
        debate_history.append({"role": "正方", "content": pro_statement})
        
        # == 裁判串场 (邀请反方) ==
        judge_crosstalk_prompt = f"""你是一位中立的裁判。正方刚刚完成了发言。
正方发言内容：“{pro_statement}”
请简单总结一下正方的观点，然后邀请反方（角色：{con_role}）进行回应或陈述。保持简洁、中立。"""
        judge_messages.append({"role": "user", "content": judge_crosstalk_prompt})
        crosstalk = get_ai_response(client, judge_model, judge_messages)
        print(f"\n--- 裁判 ---\n{crosstalk}\n")
        debate_history.append({"role": "裁判", "content": crosstalk})
        judge_messages.append({"role": "assistant", "content": crosstalk})

        # == 反方发言 ==
        con_prompt = f"""你是反方辩手，你的角色是：{con_role}。
辩论主题：“{topic}”。你的核心立场是反对这个主题。
这是你之前的发言，作为参考：{[msg['content'] for msg in debate_history if msg['role'] == '反方']}
这是你的对手（正方）的发言：{[msg['content'] for msg in debate_history if msg['role'] == '正方']}
现在轮到你发言。请根据你角色的立场，有逻辑地陈述你的观点，并针对性地反驳正方刚刚的发言：“{pro_statement}”。
请直接开始你的发言。"""
        con_messages = [{"role": "system", "content": con_system_prompt or con_prompt}]
        con_messages.extend([{"role": "user" if m["role"] == "正方" else "assistant", "content": m["content"]} for m in debate_history if m["role"] in ["正方", "反方"]])

        con_statement = get_ai_response(client, debater_model, con_messages)
        print(f"\n--- 反方 (角色: {con_role}) ---\n{con_statement}\n")
        debate_history.append({"role": "反方", "content": con_statement})

        # == 裁判串场 (准备下一轮或总结) ==
        if round_num < max_rounds:
            judge_crosstalk_prompt_2 = f"""你是一位中立的裁判。反方刚刚完成了发言。
反方发言内容：“{con_statement}”
请简单总结，并宣布进入下一轮辩论，再次邀请正方发言。"""
            judge_messages.append({"role": "user", "content": judge_crosstalk_prompt_2})
            crosstalk = get_ai_response(client, judge_model, judge_messages)
            print(f"\n--- 裁判 ---\n{crosstalk}\n")
            debate_history.append({"role": "裁判", "content": crosstalk})
            judge_messages.append({"role": "assistant", "content": crosstalk})

    # --- 最终裁决 ---
    print("==================== 辩论结束 ====================")
    judge_final_prompt = f"""你是一位专业的辩论裁判。一场关于“{topic}”的辩论刚刚结束。
以下是完整的辩论记录：
{json.dumps(debate_history, ensure_ascii=False, indent=2)}

你的任务是：
1.  首先，感谢双方辩手的精彩表现。
2.  综合双方在整个辩论过程中的逻辑严谨性、论据充分性、临场反应和角色扮演的契合度。
3.  基于上述标准，宣布哪一方获胜。
4.  详细解释你做出这个裁决的理由，具体指出获胜方在哪些方面做得更好，以及失利方可能存在的不足。
你的裁决必须公正、有说服力。"""
    judge_messages.append({"role": "user", "content": judge_final_prompt})
    final_verdict = get_ai_response(client, judge_model, judge_messages)
    print(f"\n--- 裁判最终裁决 ---\n{final_verdict}\n")
    debate_history.append({"role": "裁判最终裁决", "content": final_verdict})

    return debate_history

# --- 4. 结果保存 ---
def save_json_record(debate_history, base_filename, debate_settings):
    """将包含设置和历史的完整记录保存为 JSON 文件。"""
    filename = f"{base_filename}.json"
    record = {
        "settings": debate_settings,
        "history": debate_history
    }
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=4)
        print(f"[+] 完整的JSON记录已保存至: {filename}")
    except IOError as e:
        print(f"[!] 错误：无法写入 JSON 文件 {filename}。原因: {e}")

def save_text_record(debate_history, base_filename):
    """将辩论记录保存为易读的 TXT 文件。"""
    filename = f"{base_filename}.txt"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for message in debate_history:
                f.write(f"--- {message['role']} ---\n")
                f.write(f"{message['content']}\n\n")
        print(f"[+] 易读的文本记录已保存至: {filename}")
    except IOError as e:
        print(f"[!] 错误：无法写入文本文件 {filename}。原因: {e}")

# ==========================================================
# ================ 新增的 Markdown 保存功能 ================
# ==========================================================
def save_markdown_record(debate_history, base_filename, debate_settings):
    """将辩论记录保存为格式化的 Markdown 文件。"""
    filename = f"{base_filename}.md"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            # 写入主标题
            f.write(f"# 辩论主题：{debate_settings['topic']}\n\n")

            # 写入辩论设置作为引述块
            f.write("> **辩论设置**\n")
            f.write(">\n")
            f.write(f"> - **正方**: {debate_settings['pro_role']}\n")
            f.write(f"> - **反方**: {debate_settings['con_role']}\n")
            f.write(f"> - **最大轮数**: {debate_settings['max_rounds']}\n\n")

            f.write("---\n\n") # 水平分割线

            # 遍历并写入辩论历史
            for message in debate_history:
                role = message['role']
                content = message['content']

                # 使用三级标题表示发言者，使其突出
                f.write(f"### **{role}**\n\n")
                
                # 将发言内容放入引述块，以实现清晰的视觉分隔
                # 并正确处理内容中的换行
                formatted_content = '> ' + content.replace('\n', '\n> ')
                f.write(f"{formatted_content}\n\n")

        print(f"[+] Markdown 格式记录已保存至: {filename}")
    except IOError as e:
        print(f"[!] 错误：无法写入 Markdown 文件 {filename}。原因: {e}")


# --- 5. 主函数 ---
def main():
    """程序主入口"""
    debate_history = []
    debate_settings = {}
    try:
        config = load_config()
        client = openai.OpenAI(api_key=config['api_key'], base_url=config['base_url'])

        print("--- 欢迎来到AI自动辩论工具 ---")
        topic = input("请输入辩论主题: ")
        while True:
            try:
                max_rounds = int(input("请输入最大辩论轮数: "))
                break
            except ValueError:
                print("无效输入，请输入一个整数。")
        
        print("--- 设置双方角色信息 ---")
        pro_role = input("请输入支持方(正方)的角色描述 (例如：一位推崇自由办公的互联网公司HR): ")
        con_role = input("请输入反对方的角色描述 (例如：一位注重团队协作和管理效率的传统企业CEO): ")
        
        print("\n您可以为AI提供更底层的指令 (System Message)，留空则使用默认值。")
        pro_system_prompt = input("请输入正方的 System Message (可选): ")
        con_system_prompt = input("请输入反方的 System Message (可选): ")
        
        debate_settings = {
            'topic': topic,
            'max_rounds': max_rounds,
            'pro_role': pro_role,
            'con_role': con_role,
            'pro_system_prompt': pro_system_prompt,
            'con_system_prompt': con_system_prompt,
            'model_name': config['model_name'],
            'judge_model_name': config['judge_model_name']
        }
        
        debate_history = run_debate(client, debate_settings)

    except FileNotFoundError as e:
        print(e)
    except KeyboardInterrupt:
        print("\n[!] 用户中断了程序。")
    except Exception as e:
        print(f"\n[!] 发生未知错误: {e}")
    finally:
        if debate_history:
            # 清理主题字符串，使其可作为文件名
            safe_topic = re.sub(r'[\\/*?:"<>|]', "", topic)[:50]
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"debates/{timestamp}_{safe_topic}"
            
            # 创建debates目录 (如果不存在)
            if not os.path.exists('debates'):
                os.makedirs('debates')

            save_json_record(debate_history, base_filename, debate_settings)
            save_text_record(debate_history, base_filename)
            # ==================================================
            # ================ 调用新增的保存功能 ================
            # ==================================================
            save_markdown_record(debate_history, base_filename, debate_settings)

if __name__ == "__main__":
    main()
