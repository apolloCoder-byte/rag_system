import re

def unify_headings_to_level2(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    processed_lines = []
    for line in lines:
        stripped_line = line.strip()
        
        # 检查是否是标题行
        if stripped_line.startswith('#') and len(stripped_line) > 1 and stripped_line[1] in ['#', ' ']:
            # 计算原始标题层级（#的数量）
            level = 0
            while level < len(stripped_line) and stripped_line[level] == '#':
                level += 1
            
            # 提取标题文本（去掉#和后面的空格）
            heading_text = stripped_line[level:].strip()
            
            # 统一转换为二级标题
            new_heading = f"## {heading_text}\n"
            processed_lines.append(new_heading)
        else:
            # 非标题行直接保留
            processed_lines.append(line)
    
    # 写入处理后的内容
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(processed_lines)
    
    print(f"处理完成！所有标题已统一为二级标题，结果已保存到：{output_file}")

# 配置输入输出文件路径
input_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编3.md"    # 替换为你的输入文件路径
output_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编4.md"  # 替换为输出文件路径

# 执行处理
unify_headings_to_level2(input_path, output_path)
    