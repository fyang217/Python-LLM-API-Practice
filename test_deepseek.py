import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, APIStatusError, OpenAI


SYSTEM_PROMPT = """你是一名环境微生物学与宏基因组学研究助理。
使用严谨、客观的学术语言，明确区分已确认事实、合理推测和未知信息。
说明推测的依据和局限。证据不足时，明确指出哪些信息尚无法确认。
涉及文献时，不得编造作者、年份、DOI 或研究结论。无法核实的引文信息应标明未核实。
准确使用 ARG（抗生素抗性基因）、MGE（可移动遗传元件）、
iDNA（胞内 DNA）和 eDNA（在此语境下指胞外 DNA）等术语。
如果缩写在用户提供的材料中有不同定义，说明该材料采用的定义。"""


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("缺少 DEEPSEEK_API_KEY，请检查项目根目录下的 .env。", file=sys.stderr)
        return 1

    with OpenAI(api_key=api_key, base_url="https://api.deepseek.com") as client:
        while True:
            prompt = input("请输入你的问题（输入 exit 退出）：")
            if prompt.strip().lower() == "exit":
                break

            try:
                response = client.chat.completions.create(
                    model="deepseek-flash",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
            except APIConnectionError:
                print("无法连接到 DeepSeek API，请检查网络连接。", file=sys.stderr)
                continue
            except APIStatusError as error:
                print(f"DeepSeek API 请求失败（HTTP {error.status_code}）。", file=sys.stderr)
                continue
            except APIError:
                print("DeepSeek API 请求失败。", file=sys.stderr)
                continue

            if not response.choices or not response.choices[0].message.content:
                print("DeepSeek API 未返回文本回答。", file=sys.stderr)
                continue

            answer = response.choices[0].message.content
            print(answer.replace(api_key, "[已隐藏]"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
