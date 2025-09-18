import os
# 设置新的缓存目录
os.environ["HF_HOME"] = "D:/Applications/develop/huggingface_cache"
os.environ["HUGGINGFACE_HUB_CACHE"] = "D:/Applications/develop/huggingface_cache"

from loguru import logger

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
import tiktoken

import torch
print(torch.cuda.is_available())


class PDFProcessor:
    def __init__(self):

        # 项目根路径
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        # resource文件夹路径
        self.resource_path = os.path.join(self.project_root, "src", "resource")
        # markdown文件夹路径
        self.markdown_path = os.path.join(self.resource_path, "markdown")
        # pdf文件夹路径
        self.pdf_path = os.path.join(self.resource_path, "pdf")

        accelerator_options = AcceleratorOptions(
            num_threads=8, device=AcceleratorDevice.CUDA
        )
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = accelerator_options
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )
    
    def convert_pdf_to_markdown(self, file_name):
        pdf_file = file_name + ".pdf"
        print(pdf_file)
        file_path = os.path.join(self.pdf_path, pdf_file)
        logger.info(f"开始处理文件：{file_path}")
        try:
            markdown_document = self.converter.convert(file_path).document.export_to_markdown()
            logger.info("PDF转换为markdown成功")
        except Exception as e:
            logger.error("PDF转换为markdown失败")
            raise RuntimeError(f"PDF转换错误: {e}")
        
        logger.info("开始保存转换结果")
        try:
            markdown_file = file_name + ".md"
            print(markdown_file)
            markdown_file_path = os.path.join(self.markdown_path, markdown_file)
            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_document)
                logger.info(f"Markdown已保存")
        except Exception as e:
            logger.error("保存结果失败")
            raise RuntimeError(f"保存结果失败：{e}")
        
        return markdown_document


if __name__ == "__main__":
    pdf_processor = PDFProcessor()
    pdf_processor.convert_pdf_to_markdown("中央及银保监会金融监管政策文件汇编")

# 该脚本的使用说明：
# resource文件夹下有markdown文件夹和pdf文件夹
# 这个脚本的作用是使用docling将pdf文件夹下的文件解析为markdown，并存储为同名的md文件。
# convert_pdf_to_markdown的参数填入文件的名称即可，不需要加后缀
# 使用该脚本时，通过管理员运行的powershell运行。
