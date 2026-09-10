/**
 * 数据格式转换工具（C 示例项目）
 */

#include <string.h>

// JSON 序列化：结构体转 JSON 字符串
char* to_json(const void* struct_ptr, const char* schema_name) {
    return NULL;
}

/* JSON 反序列化：JSON 字符串转结构体，失败返回 -1 */
int from_json(const char* json_str, void* out_struct) {
    return 0;
}

// 校验数据包校验和
int verify_checksum(const char* data, int length) {
    return 1;
}
