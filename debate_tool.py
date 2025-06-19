import os
import json
import datetime
import configparser
from openai import OpenAI

# --- 1. 配置加载 ---
def load_config():
    """从 config.ini 加载配置"""
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        raise FileNotFoundError("错误：未找到 config.ini 配置文件。请根据说明创建该文件。")
    config.read('config.ini', encoding='utf-8')
    return {
        'base_url': config['openai']['base_url'],
        'api_key': config['openai']['api_key'],
        'model_name': config['openai']['model_name'],
        'judge_model_name': config['openai']['judge_model_name']
    }

# --- 2. AI 代理类 ---
class AIAgent:
    """一个通用的AI代理，可以代表辩手或裁判"""
    def __init__(self, client, model, system_message):
        self.client = client
        self.model = model
        self.system_message = system_message

    def speak(self, history):
        """根据对话历史生成回应"""
        messages = [{"role": "system", "content": self.system_message}] + history
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7, # 增加一点创造性
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"调用API时出错: {e}"

# --- 3. 辩论记录保存 ---
def save_debate_records(topic, history):
    """将辩论记录保存为 JSON 和 TXT 文件"""
    # 确保 debates 目录存在
    if not os.path.exists('debates'):
        os.makedirs('debates')

    # 创建一个安全的文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(x for x in topic if x.isalnum() or x in " -_").rstrip()
    base_filename = f"debates/{timestamp}_{safe_topic}"

    # 保存为 JSON 格式
    json_filename = f"{base_filename}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    print(f"\n[+] 完整的JSON记录已保存至: {json_filename}")

    # 保存为易读的 TXT 格式
    txt_filename = f"{base_filename}.txt"
    with open(txt_filename, 'w', encoding='utf-8') as f:
        f.write(f"辩论主题: {topic}\n")
        f.write("="*40 + "\n\n")
        for entry in history:
            role = entry.get('role_name', entry.get('role'))
            content = entry.get('content', '')
            f.write(f"[{role}]:\n{content}\n\n")
            f.write("-"*40 + "\n")
    print(f"[+] 易读的文本记录已保存至: {txt_filename}")


# --- 4. 主辩论流程 ---
def run_debate(client, model_name, judge_model_name):
    """运行整个辩论流程"""
    print("--- 欢迎来到AI自动辩论工具 ---")

    # --- 用户输入 ---
    topic = input("请输入辩论主题: ")
    max_rounds = int(input("请输入最大辩论轮数: "))

    print("\n--- 设置双方角色信息 ---")
    pro_desc = input("请输入支持方(正方)的角色描述 (例如：一位乐观的技术专家): ")
    con_desc = input("请输入反对方的角色描述 (例如：一位谨慎的社会伦理学者): ")
    
    # 参与人数 (当前版本默认为1v1，为未来扩展保留)
    # num_participants = int(input("请输入参与辩论的人数 (目前仅支持2人): "))
    # if num_participants != 2:
    #     print("当前版本仅支持2人辩论，将按2人进行。")

    # 可选的 System Message
    print("\n您可以为AI提供更底层的指令 (System Message)，留空则使用默认值。")
    pro_sm_override = input("请输入正方的 System Message (可选): ")
    con_sm_override = input("请输入反方的 System Message (可选): ")

    # --- 初始化 AI 代理 ---
    # 默认 System Message
    default_pro_sm = f"你是一位辩手，你的身份是“{pro_desc}”。你的任务是清晰、有说服力地论证“{topic}”这一观点的正确性。请使用事实、逻辑和例子来支持你的论点，并有力地反驳对方的观点。保持你的角色，观点要鲜明。"
    default_con_sm = f"你是一位辩手，你的身份是“{con_desc}”。你的任务是清晰、有说服力地反对“{topic}”这一观点。请使用事实、逻辑和例子来支持你的论点，并有力地反驳对方的观点。保持你的角色，观点要鲜明。"
    referee_sm = f"你是一位经验丰富、绝对中立的辩论裁判。你的任务是主持一场关于“{topic}”的辩论。辩论双方分别是正方({pro_desc})和反方({con_desc})。你需要：1.宣布辩论开始。2.在每轮之间进行简短的串场，引导讨论。3.在辩论结束后，根据双方的论证质量、逻辑严谨性和说服力，宣布获胜方，并给出清晰、公正的评判理由。你的评判必须只基于本场辩论的表现。"

    pro_system_message = pro_sm_override if pro_sm_override else default_pro_sm
    con_system_message = con_sm_override if con_sm_override else default_con_sm

    pro_agent = AIAgent(client, model_name, pro_system_message)
    con_agent = AIAgent(client, model_name, con_system_message)
    referee_agent = AIAgent(client, judge_model_name, referee_sm)

    # --- 开始辩论 ---
    history = []
    print("\n" + "="*20 + " 辩论开始 " + "="*20)
    
    # 裁判开场
    print("\n--- 裁判 ---")
    opening_statement = referee_agent.speak(history)
    print(opening_statement)
    history.append({"role": "assistant", "role_name": "裁判", "content": opening_statement})
    
    # 辩论循环
    for i in range(1, max_rounds + 1):
        print("\n" + f"--- 第 {i} 轮 ---")
        
        # 正方发言
        print(f"\n--- 正方 ({pro_desc}) ---")
        prompt_pro = "现在轮到正方发言。请陈述你的观点或反驳对方。"
        history.append({"role": "user", "content": prompt_pro})
        pro_statement = pro_agent.speak(history)
        print(pro_statement)
        history.pop() # 移除临时提示
        history.append({"role": "assistant", "role_name": f"正方 ({pro_desc})", "content": pro_statement})

        # 反方发言
        print(f"\n--- 反方 ({con_desc}) ---")
        prompt_con = "现在轮到反方发言。请陈述你的观点或反驳对方。"
        history.append({"role": "user", "content": prompt_con})
        con_statement = con_agent.speak(history)
        print(con_statement)
        history.pop() # 移除临时提示
        history.append({"role": "assistant", "role_name": f"反方 ({con_desc})", "content": con_statement})
        
        # 裁判串场 (可选，最后一轮后不再串场)
        if i < max_rounds:
            print("\n--- 裁判 ---")
            transition_prompt = "请对刚才的第"+str(i)+"轮进行一个简短的总结，并宣布下一轮开始。"
            history.append({"role": "user", "content": transition_prompt})
            transition_statement = referee_agent.speak(history)
            print(transition_statement)
            history.pop()
            history.append({"role": "assistant", "role_name": "裁判", "content": transition_statement})


    # --- 宣布结果 ---
    print("\n" + "="*20 + " 辩论结束 " + "="*20)
    print("\n--- 裁判最终裁决 ---")
    
    judgement_prompt = "辩论已结束。请根据双方的整体表现，综合评估其论证的逻辑性、说服力、证据支持和反驳能力，宣布获胜方，并提供详细、公正的评判理由。"
    history.append({"role": "user", "content": judgement_prompt})
    final_judgement = referee_agent.speak(history)
    print(final_judgement)
    history.pop()
    history.append({"role": "assistant", "role_name": "裁判 (最终裁决)", "content": final_judgement})

    # --- 保存记录 ---
    save_debate_records(topic, history)


# --- 5. 程序入口 ---
if __name__ == "__main__":
    try:
        config = load_config()
        # 验证API Key是否存在
        if 'xxxxxxxx' in config['api_key'] or not config['api_key']:
             print("错误：请在 config.ini 文件中设置您的 OpenAI API Key。")
        else:
            # 初始化 OpenAI 客户端
            # 注意：请确保已安装 openai 库 (pip install openai)
            client = OpenAI(
                api_key=config['api_key'],
                base_url=config['base_url'],
            )
            run_debate(
                client=client,
                model_name=config['model_name'],
                judge_model_name=config['judge_model_name']
            )

    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"程序运行出现未知错误: {e}")

