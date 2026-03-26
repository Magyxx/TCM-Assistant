from app.chains.mvp_chain import chain

def main():
    print("中医问诊辅助系统 MVP，输入 exit 退出。")
    while True:
        text = input("用户: ").strip()
        if text.lower() == "exit":
            break

        response = chain.invoke({"user_input": text})
        print("助手:")
        print(response.content)
        print("-" * 50)

if __name__ == "__main__":
    main()