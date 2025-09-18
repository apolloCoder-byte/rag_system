def merge_all_headings(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 存储当前各级标题内容，索引0表示一级标题，1表示二级，以此类推
    heading_levels = []
    processed_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        
        # 检查是否是标题行
        if stripped_line.startswith('#') and len(stripped_line) > 1 and stripped_line[1] in ['#', ' ']:
            # 计算标题层级（#的数量）
            level = 0
            while level < len(stripped_line) and stripped_line[level] == '#':
                level += 1
            
            # 提取标题文本（去掉#和后面的空格）
            heading_text = stripped_line[level:].strip()
            
            # 调整标题层级列表
            if level - 1 < len(heading_levels):
                # 如果当前层级已存在，截断后面的层级
                heading_levels = heading_levels[:level - 1]
            
            # 添加当前标题到层级列表
            heading_levels.append(heading_text)
            
            # 拼接所有层级标题
            merged_text = '_'.join(heading_levels)
            
            # 生成新的标题行
            new_heading = '#' * level + ' ' + merged_text + '\n'
            processed_lines.append(new_heading)
        else:
            # 非标题行直接保留
            processed_lines.append(line)
    
    # 写入处理后的内容
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(processed_lines)

# 配置输入输出文件路径
input_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编.md"
output_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编1.md"

# 执行处理
merge_all_headings(input_path, output_path)
print(f"处理完成！结果已保存到：{output_path}")
