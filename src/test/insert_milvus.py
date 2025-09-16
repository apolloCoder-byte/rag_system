import asyncio
from src.utils.embedding import get_text_embeddings
from src.services.milvus import milvus_service

async def test1():
    qa_pairs = [
        {
            "question": "什么是ETF？",
            "answer": "ETF（交易所交易基金）是一种跟踪特定指数的开放式基金，可在交易所像股票一样交易。"
        },
        {
            "question": "市盈率（PE）如何计算？",
            "answer": "市盈率=股价÷每股收益，反映投资者为公司每1元利润支付的价格。"
        },
        {
            "question": "什么是对冲基金？",
            "answer": "对冲基金是一种采用复杂投资策略（如卖空、杠杆）追求绝对收益的私募投资基金。"
        },
        {
            "question": "美联储加息对股市有何影响？",
            "answer": "加息通常提高企业融资成本，可能抑制盈利增长，同时吸引资金从股市流向债市，对股市形成压力。"
        },
        {
            "question": "可转债的主要特点是什么？",
            "answer": "可转债兼具债券和股票特性，持有人可在一定条件下将其转换为公司股票，具有债底保护和股性收益潜力。"
        }
    ]

    for i, qa in enumerate(qa_pairs):
        question = qa.get("question")
        vector = get_text_embeddings(question)
        qa["question_embedding"] = vector

    await milvus_service.insert_data("memory", qa_pairs)


async def test2():
    question = "什么是可转债？"
    vector = get_text_embeddings(question)
    result = await milvus_service.search_data_by_single_vector(
        "memory",vector,"question_embedding",["question","answer"],3
    )
    for item in result:
        print(item)
        print("\n")


if __name__ == "__main__":
    asyncio.run(test2())
    