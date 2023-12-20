import random
import string
import argparse
import os 

RANDOM_BASE_SET = ''
def generate_same_char(c, output_file, size):
    # 删除原有文件
    os.system('rm -rf {}'.format(output_file))
    # 1mb内容
    to_be_written = c * 1000 * 1000
    f = open(output_file,'a')
    
    for i in range(int(1000 * size)):
        f.write(to_be_written)
        f.flush()
    f.close()

def _do_generate_random_char(randomlength):
    global RANDOM_BASE_SET
    random_str = ''
    
    length = len(RANDOM_BASE_SET) - 1
    for i in range(randomlength):
        random_str += RANDOM_BASE_SET[random.randint(0, length)]
    return random_str

def generate_random_char(output_file, size):
    global RANDOM_BASE_SET
    os.system('rm -rf {}'.format(output_file))
    for i in range(1, 0x100):
        # ascii码共256个字符
        RANDOM_BASE_SET += chr(i)
    
    to_be_written_base = _do_generate_random_char(1000 * 1000)
    f = open(output_file,'ab')
    
    for i in range(int(1000 * size)):
       
        random_num = random.randint(0, 1000)
        # 为什么是1000+256,感觉数目有问题
        to_be_written = to_be_written_base[0 : random_num] + to_be_written_base[random_num] * 24 + to_be_written_base[random_num + 24:]
        
        f.write(to_be_written.encode('latin1'))
        f.flush()
    
    f.close()

if __name__ == '__main__':
    # 创建一个解析对象
    parser = argparse.ArgumentParser('Generate a file')
    # 添加关注的参数和选项
    parser.add_argument('-s','--size', help = 'type in 1 for 1G', type = float, default=2)
    parser.add_argument('-c','--char', type = str, default='0')
    parser.add_argument('-o','--output', type = str, default='output.bin')
    parser.add_argument('generate_type', type = str, default=False, choices = ['generate_same_char', 'generate_random_char'])
    args = parser.parse_args()
    
    if args.generate_type == 'generate_same_char':
        generate_same_char(args.char, args.output, args.size)
    elif args.generate_type == 'generate_random_char':
        generate_random_char(args.output, args.size)

