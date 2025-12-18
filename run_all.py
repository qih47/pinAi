import subprocess
import threading

def run_app():
    print("🚀 Menjalankan Document Parser di port 5001...")
    subprocess.call(["python", "main_parser.py"])

def run_main():
    print("🤖 Menjalankan RAG AI Assistant di port 5000...")
    subprocess.call(["python", "main_rag.py"])

if __name__ == "__main__":
    t1 = threading.Thread(target=run_app)
    t2 = threading.Thread(target=run_main)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
