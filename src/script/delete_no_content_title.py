# import re

# def remove_empty_headings(input_file, output_file):
#     with open(input_file, 'r', encoding='utf-8') as f:
#         lines = f.readlines()
    
#     # 解析文档结构，识别所有标题及其位置和层级
#     headings = []
#     for i, line in enumerate(lines):
#         stripped_line = line.strip()
#         if stripped_line.startswith('#') and len(stripped_line) > 1 and stripped_line[1] in ['#', ' ']:
#             # 计算标题层级
#             level = 0
#             while level < len(stripped_line) and stripped_line[level] == '#':
#                 level += 1
#             heading_text = stripped_line[level:].strip()
#             headings.append({
#                 'index': i,
#                 'level': level,
#                 'text': heading_text,
#                 'line': line
#             })
    
#     # 确定每个标题是否有内容或有保留的子标题
#     heading_status = {h['index']: False for h in headings}  # False表示可删除，True表示需保留
    
#     # 从最低级别标题开始向上分析
#     # 按层级从高到低排序
#     headings_sorted = sorted(headings, key=lambda x: -x['level'])
    
#     for heading in headings_sorted:
#         heading_index = heading['index']
#         heading_level = heading['level']
        
#         # 查找下一个同级或更高级别的标题位置
#         next_heading_index = None
#         for h in headings:
#             if h['index'] > heading_index and h['level'] <= heading_level:
#                 next_heading_index = h['index']
#                 break
        
#         # 如果没有更后面的标题，则以下一个标题位置为文档末尾
#         end_index = next_heading_index if next_heading_index is not None else len(lines)
        
#         # 检查标题下是否有实际内容（非标题行且非空行）
#         has_content = False
#         for i in range(heading_index + 1, end_index):
#             line = lines[i].strip()
#             # 非标题且不是空行的内容视为有效内容
#             if line and not (line.startswith('#') and len(line) > 1 and line[1] in ['#', ' ']):
#                 has_content = True
#                 break
        
#         # 检查是否有需要保留的子标题
#         has_kept_subheading = False
#         for h in headings:
#             if (h['index'] > heading_index and 
#                 (next_heading_index is None or h['index'] < next_heading_index) and 
#                 h['level'] > heading_level and 
#                 heading_status[h['index']]):
#                 has_kept_subheading = True
#                 break
        
#         # 如果有内容或有保留的子标题，则保留当前标题
#         if has_content or has_kept_subheading:
#             heading_status[heading_index] = True
    
#     # 生成处理后的内容
#     processed_lines = []
#     heading_indices = {h['index'] for h in headings}
    
#     for i, line in enumerate(lines):
#         # 如果是标题且标记为可删除，则跳过
#         if i in heading_indices and not heading_status[i]:
#             continue
#         # 否则保留该行
#         processed_lines.append(line)
    
#     # 写入处理后的文件
#     with open(output_file, 'w', encoding='utf-8') as f:
#         f.writelines(processed_lines)
    
#     print(f"处理完成！结果已保存到：{output_file}")

# # 配置输入输出文件路径
# input_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编1.md"    # 替换为你的输入文件路径
# output_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编2.md"  # 替换为输出文件路径

# # 执行处理
# remove_empty_headings(input_path, output_path)

import re

def keep_lowest_content_headings(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 解析所有标题
    headings = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#') and len(stripped) > 1 and stripped[1] in ['#', ' ']:
            level = 0
            while level < len(stripped) and stripped[level] == '#':
                level += 1
            text = stripped[level:].strip()
            headings.append({
                'index': i,
                'level': level,
                'text': text,
                'line': line
            })
    
    # 标记需要保留的标题（仅最低层级且有内容的标题）
    keep_indices = set()
    for heading in headings:
        idx = heading['index']
        level = heading['level']
        
        # 找下一个同级/更高级标题的位置
        next_heading_idx = None
        for h in headings:
            if h['index'] > idx and h['level'] <= level:
                next_heading_idx = h['index']
                break
        end_idx = next_heading_idx if next_heading_idx else len(lines)
        
        # 检查是否有内容
        has_content = False
        for i in range(idx + 1, end_idx):
            line = lines[i].strip()
            if line and not (line.startswith('#') and len(line) > 1 and line[1] in ['#', ' ']):
                has_content = True
                break
        
        # 检查是否有子标题（如果有子标题，则当前标题不是最低层级）
        has_subheading = False
        for h in headings:
            if h['index'] > idx and (next_heading_idx is None or h['index'] < next_heading_idx) and h['level'] > level:
                has_subheading = True
                break
        
        # 仅当“无+子标题”且“有内容”时，保留当前标题
        if not has_subheading and has_content:
            keep_indices.add(idx)
    
    # 生成处理后内容
    processed = []
    heading_indices = {h['index'] for h in headings}
    for i, line in enumerate(lines):
        if i in heading_indices and i not in keep_indices:
            continue
        processed.append(line)
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(processed)
    print(f"结果已保存到：{output_file}")

# 替换为实际路径
input_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编1.md"
output_path = r"D:\code\llm\todolist\src\resource\markdown\中央及银保监会金融监管政策文件汇编3.md"

keep_lowest_content_headings(input_path, output_path)