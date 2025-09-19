"""这个脚本的作用是处理转换为markdown的md文件"""

import os
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_milvus import Milvus
from loguru import logger

class ProcessMarkdown:
    def __init__(self, chunk_size=6000, chunk_overlap=2000):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.markdown_path = os.path.join(self.project_root, "src", "resource", "markdown")

        headers_to_split_on = [
            ("##", "title"),
        ]
        self.split_markdown = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on, 
            strip_headers=False  # 这个参数保留标题
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        # vector database
        embedding_fn = DashScopeEmbeddings(
            model="text-embedding-v4",
            dashscope_api_key="使用百炼的api key"  # 使用百炼的api key
        )
        self.vector_db = Milvus(
            embedding_function=embedding_fn,
            collection_name="knowledge",
            collection_description="中央及银保监会金融监管政策文件汇编",
            connection_args={
                "uri": "http://localhost:19530",
                "db_name": "finance"
            },
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE"
            },
            auto_id=True
        )
    
    def load_markdown_content(self, file_name):
        """读取markdown文件中的内容"""
        file_path = os.path.join(self.markdown_path, f"{file_name}.md")
        with open(file_path, 'r', encoding='utf-8') as file:
            markdown_document = file.read()
            return markdown_document

    def split_markdown_file(self, content):
        """根据markdown的层级结构进行划分"""
        md_header_splits = self.split_markdown.split_text(content)
        return md_header_splits

    def embedding_and_restore_batch(self, documents):
        """将documents分批次向量化和存储到知识库中"""
        no_success = []
        num = len(documents)
        batch_size = 10  # 文档写的
        for i in range(0, num, batch_size):
            batch_docs = documents[i:i+batch_size]
            try:
                # 对单批文档进行处理，异常仅影响当前批次
                self.vector_db.add_documents(batch_docs)
                logger.info(f"成功处理第 {i//batch_size + 1} 批文档（{len(batch_docs)} 个）")
            except Exception as e:
                # 记录当前批次失败的文档和具体错误
                no_success.extend(batch_docs)
                logger.error(f"处理第 {i//batch_size + 1} 批文档失败：{str(e)}", exc_info=True)
                # 继续处理下一批次，避免整体中断
        
        logger.info(f"所有文档处理完成，成功 {num - len(no_success)} 个，失败 {len(no_success)} 个")
        return no_success
    
    def embedding_and_restore_single(self, documents):
        """"对出现问题的批次的document进行处理"""
        processed_docs = []
        batch_size = 10
        for i, item in enumerate(documents):
            try:
                self.vector_db.add_documents([item])
                logger.info(f"成功处理第{i+1}/{len(documents)}个")
            except Exception as e:
                logger.error(f"第{i+1}个发生错误，开始分割")
                sub_docs = self.text_splitter.split_documents([item])
                processed_docs.extend(sub_docs)
                logger.info(f"第{i+1}个分割完成")
        logger.info(f"分割出{len(processed_docs)}个子文档")
        for i in range(0, len(processed_docs), batch_size):
            batch_docs = processed_docs[i:i+batch_size]
            self.vector_db.add_documents(batch_docs)
            logger.info(f"成功处理第{i+1}/{len(processed_docs)}个")
        
        logger.info("所有的都处理完毕")

    def print_doc(self, documents, num=None):
        """打印，看一下document的内容"""
        for i, doc in enumerate(documents):
            if num and i == num:
                break
            print(f"==========={i+1}=================")
            print(doc)
            print("\n")

    def forward(self, file_name):
        """执行函数"""
        contents = self.load_markdown_content(file_name)
        documents = self.split_markdown_file(contents)
        # self.print_doc(documents)
        no_success_documents = self.embedding_and_restore_batch(documents)
        if len(no_success_documents) > 0:
            self.embedding_and_restore_single(no_success_documents)

if __name__ == "__main__":
    process = ProcessMarkdown()
    process.forward("中央及银保监会金融监管政策文件汇编")
