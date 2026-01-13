import requests
import json
import schedule
import time
from datetime import datetime
import logging

# 配置日志，方便查看程序运行状态
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bilibili_video_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# B站搜索API相关配置
BASE_URL = "https://api.bilibili.com/x/web-interface/search/type"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://search.bilibili.com/",
    "Cookie": "buvid3=DA30582E-68B3-65DB-E5A6-76E09B57E07B26829infoc; b_nut=1753082426; _uuid=296BF48D-8D78-556C-9493-10BA310499416423246infoc; enable_web_push=DISABLE; theme-tip-show=SHOWED; rpdid=0zbfvRPZtl|NkukUwIe|4uh|3w1UDKQh; theme-avatar-tip-show=SHOWED; hit-dyn-v2=1; LIVE_BUVID=AUTO2317536253907372; DedeUserID=4353176; DedeUserID__ckMd5=1016374f804c7b87; CURRENT_QUALITY=112; buvid4=2C6C61B1-94CB-4FF1-99D5-97F6A626E0AD57889-024082819-fc28ZhpCIjPTWQYSaHgmrsnYDZ8ojZY26wfJ+7jbqR6HMLV+uFvh/6Rs2ugTQhdY; home_feed_column=5; PVID=1; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Njg1MDg0MTMsImlhdCI6MTc2ODI0OTE1MywicGx0IjotMX0.FL83_5PQSdxPBqMhNiLQHBAb0by8rzSLy2RtyuO_W1w; bili_ticket_expires=1768508353; SESSDATA=a6e0948a%2C1783801214%2C1d577%2A12CjD1McunOd6-jF8jg5LG4XZ3-ZE6BGKen9zQVm78KAiXIRiuDKQF_h_ybxiWhhnkPSsSVjd2V19rYjluQU1xQjRpZXowSVBRa3lfUVFKaC1OaHNiWTdHQXpIS2dGTmxsR3M2dzhWVHhUZnlIbHJycDd0OFVhN2VHZHUyZFRGenhMYkZMZThWanpnIIEC; bili_jct=840a58c2024ff32ba3abaa595ce2dba5; bmg_af_switch=1; bmg_src_def_domain=i2.hdslb.com; sid=8rj4pn0o; b_lsid=105BB69FE_19BB6445252; bp_t_offset_4353176=1157284899321806848; CURRENT_FNVAL=4048; fingerprint=83bcda3815fdb23a78b231094071dcec; buvid_fp_plain=undefined; buvid_fp=83bcda3815fdb23a78b231094071dcec; browser_resolution=1507-1282"
}

# 定义屏蔽词列表
BLOCK_WORDS = ["谭"]

def get_top5_videos():
    """
    获取B站上包含"三酒 豌豆"且不包含屏蔽词的前5个视频
    """
    params = {
        "keyword": "三酒 豌豆",  # 搜索关键词
        "search_type": "video",  # 搜索类型为视频
        "order": "totalrank",    # 综合排序
        "page": 1,
        "pagesize": 20  # 先获取更多结果，再过滤屏蔽词，保证能拿到5条有效数据
    }
    
    try:
        # 发送请求
        response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()  # 抛出HTTP错误
        
        # 解析响应数据
        data = response.json()
        if data.get("code") != 0:
            logging.error(f"API返回错误: {data.get('message')}")
            return None
        
        # 提取并过滤视频核心信息（排除含屏蔽词的内容）
        video_list = []
        for item in data.get("data", {}).get("result", []):
            # 提取基础信息并清理标题
            title = item.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", "")
            author = item.get("author", "")
            
            # 检查是否包含屏蔽词
            contains_block_word = any(word in title or word in author for word in BLOCK_WORDS)
            if contains_block_word:
                logging.info(f"过滤含屏蔽词的视频：标题={title}，UP主={author}")
                continue
            
            # 组装视频信息
            video_info = {
                "标题": title,
                "UP主": author,
                "播放量": item.get("play", 0),
                "弹幕数": item.get("danmaku", 0),
                "发布时间": datetime.fromtimestamp(item.get("pubdate", 0)).strftime("%Y-%m-%d %H:%M:%S"),
                "视频链接": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            video_list.append(video_info)
            
            # 凑够5条即停止
            if len(video_list) >= 20:
                break
        
        # 若过滤后不足5条，记录警告
        if len(video_list) < 5:
            logging.warning(f"过滤屏蔽词后仅获取到{len(video_list)}条有效视频（目标5条）")
        
        # 保存到JSON文件
        save_to_file(video_list)
        logging.info(f"成功获取并保存{len(video_list)}个无屏蔽词的视频信息")
        return video_list
        
    except requests.exceptions.RequestException as e:
        logging.error(f"网络请求失败: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"程序执行异常: {str(e)}", exc_info=True)
        return None

def save_to_file(video_list):
    """
    将视频信息保存到JSON文件
    """
    filename = f"三酒豌豆视频_{datetime.now().strftime('%Y%m%d')}.json"
    
    # 读取历史数据（如果需要追加）
    try:
        with open("三酒豌豆视频汇总.json", "r", encoding="utf-8") as f:
            history_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history_data = []
    
    # 添加新数据
    history_data.append({
        "更新日期": datetime.now().strftime("%Y-%m-%d"),
        "视频列表": video_list
    })
    
    # 保存当日数据
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(video_list, f, ensure_ascii=False, indent=4)
    
    # 保存汇总数据
    with open("三酒豌豆视频汇总.json", "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=4)

def job():
    """
    定时任务执行的函数
    """
    logging.info("开始执行每日视频获取任务")
    result = get_top5_videos()
    if result:
        print("\n今日获取的无屏蔽词前N个视频：")
        for i, video in enumerate(result, 1):
            print(f"\n{i}. 标题：{video['标题']}")
            print(f"   UP主：{video['UP主']}")
            print(f"   播放量：{video['播放量']}")
            print(f"   链接：{video['视频链接']}")
    else:
        logging.warning("视频获取失败")

if __name__ == "__main__":
    # 立即执行一次（测试用）
    logging.info("程序启动，首次执行视频获取任务")
    job()
    
    # 配置定时任务：每天0点执行
    schedule.every().day.at("00:00").do(job)
    logging.info("定时任务已配置，每天0点自动更新视频信息")
    
    # 保持程序运行
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次任务