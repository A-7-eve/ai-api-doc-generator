---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'b5d8182c-0ec0-4cab-94f2-eda849ee7f8b'
  PropagateID: 'b5d8182c-0ec0-4cab-94f2-eda849ee7f8b'
  ReservedCode1: 'f9c52160-c3f2-4c01-a0ac-e273948568c4'
  ReservedCode2: 'f9c52160-c3f2-4c01-a0ac-e273948568c4'
---

# spring-petclinic 接口文档
> 由 AI 辅助接口文档自动生成系统生成

---

## OwnerController

### 1. 显示新增宠物主人表单页面
- **接口路径**: `GET /owners/new`
- **方法名**: `initCreationForm`
- **返回类型**: `String`

---

### 2. 提交新增宠物主人信息，校验通过后保存并重定向到主人详情页
- **接口路径**: `POST /owners/new`
- **方法名**: `processCreationForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| owner | Owner | - | 是 | 主人实体对象，包含姓名、地址、城市、电话 | {"firstName":"James","lastName":"Carter","address":"110 W. Liberty St.","city":"Madison","telephone":"6085551023"} |

**请求示例**:
```json
{"firstName":"James","lastName":"Carter","address":"110 W. Liberty St.","city":"Madison","telephone":"6085551023"}
```

**响应示例**:
```json
302 redirect → /owners/{ownerId}
```

**边界场景**:
- firstName 或 lastName 为空时校验失败，返回表单页
- telephone 格式不正确时校验失败

**错误码**:

| 码 | 说明 |
|----|------|
| 200 | 校验失败时返回表单页面(非错误码) |

---

### 3. 显示按姓氏搜索宠物主人的表单页面
- **接口路径**: `GET /owners/find`
- **方法名**: `initFindForm`
- **返回类型**: `String`

---

### 4. 按姓氏查询宠物主人列表，无参数时返回全部记录
- **接口路径**: `GET /owners`
- **方法名**: `processFindForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| owner | Owner | - | 否 | 包含 lastName 的查询条件对象 | {"lastName":"Davis"} |

**请求示例**:
```json
{"lastName":"Davis"}
```

**响应示例**:
```json
302 redirect → /owners/{ownerId}（单人）或 owners/ownersList（多人）
```

**边界场景**:
- lastName 为空时返回所有主人
- 查询结果为空时提示 not found
- 查询结果唯一时重定向到详情页
- 查询结果多条时返回列表页

---

### 5. 显示编辑指定宠物主人信息的表单页面
- **接口路径**: `GET /owners/{ownerId}/edit`
- **方法名**: `initUpdateOwnerForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| ownerId | int | path | 是 | 主人记录ID | 1 |

**边界场景**:
- ownerId 不存在时可能抛出异常

**错误码**:

| 码 | 说明 |
|----|------|
| 404 | 主人记录不存在 |

---

### 6. 提交更新后的宠物主人信息，校验通过后保存并重定向到详情页
- **接口路径**: `POST /owners/{ownerId}/edit`
- **方法名**: `processUpdateOwnerForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| owner | Owner | - | 是 | 更新后的主人实体对象 | {"firstName":"Betty","lastName":"Davis","address":"638 Cardinal Ave.","city":"Sun Prairie","telephone":"6085551749"} |
| ownerId | int | path | 是 | 主人记录ID | 1 |

**请求示例**:
```json
{"firstName":"Betty","lastName":"Davis","address":"638 Cardinal Ave.","city":"Sun Prairie","telephone":"6085551749"}
```

**响应示例**:
```json
302 redirect → /owners/{ownerId}
```

**边界场景**:
- 字段校验失败时返回编辑表单
- ownerId 与路径参数不一致时以路径参数为准

---

### 7. 根据主人ID查询并展示宠物主人及其宠物详情
- **接口路径**: `GET /owners/{ownerId}`
- **方法名**: `showOwner`
- **返回类型**: `ModelAndView`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| ownerId | int | path | 是 | 主人记录ID | 1 |

**响应示例**:
```json
{"id":1,"firstName":"George","lastName":"Franklin","address":"110 W. Liberty St.","city":"Madison","telephone":"6085551023","pets":[{"name":"Leo","birthDate":"2010-09-07","type":"cat"}]}
```

**边界场景**:
- ownerId 为负数或 0 时可能返回空数据
- ownerId 不存在时页面显示空

**错误码**:

| 码 | 说明 |
|----|------|
| 404 | 主人记录不存在 |

---

## PetController

### 8. 显示为指定主人新增宠物的表单页面
- **接口路径**: `GET /owners/{ownerId}/pets/new`
- **方法名**: `initCreationForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| owner | Owner | - | 是 | - | - |

---

### 9. 提交新增宠物信息，校验通过后保存并重定向到主人详情页
- **接口路径**: `POST /owners/{ownerId}/pets/new`
- **方法名**: `processCreationForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| owner | Owner | - | 是 | - | - |
| pet | Pet | - | 是 | - | - |

**请求示例**:
```json
{"name":"Max","birthDate":"2020-01-15","type":"dog"}
```

**响应示例**:
```json
302 redirect → /owners/{ownerId}
```

**边界场景**:
- name 为空校验失败
- birthDate 为未来日期校验失败
- type 未选择校验失败

---

### 10. 显示编辑指定宠物信息的表单页面
- **接口路径**: `GET /owners/{ownerId}/pets/{petId}/edit`
- **方法名**: `initUpdateForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| petId | int | path | 是 | - | - |

**边界场景**:
- petId 不存在时可能抛出异常

---

### 11. 提交更新后的宠物信息，校验通过后保存并重定向到主人详情页
- **接口路径**: `POST /owners/{ownerId}/pets/{petId}/edit`
- **方法名**: `processUpdateForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| pet | Pet | - | 是 | - | - |
| owner | Owner | - | 是 | - | - |

**请求示例**:
```json
{"name":"Max","birthDate":"2020-01-15","type":"dog"}
```

**响应示例**:
```json
302 redirect → /owners/{ownerId}
```

**边界场景**:
- 字段校验失败时返回编辑表单

---

## VisitController

### 12. 显示为指定宠物新增就诊记录的表单页面
- **接口路径**: `GET /owners/*/pets/{petId}/visits/new`
- **方法名**: `initNewVisitForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| petId | int | path | 是 | 宠物记录ID | 1 |

**边界场景**:
- petId 不存在时可能抛出异常

---

### 13. 提交新增就诊记录，校验通过后保存并重定向到主人详情页
- **接口路径**: `POST /owners/{ownerId}/pets/{petId}/visits/new`
- **方法名**: `processNewVisitForm`
- **返回类型**: `String`

**请求参数**:

| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|------|
| visit | Visit | - | 是 | 就诊记录对象，包含日期和描述 | {"date":"2026-08-24","description":"Annual checkup"} |

**请求示例**:
```json
{"date":"2026-08-24","description":"Annual checkup"}
```

**响应示例**:
```json
302 redirect → /owners/{ownerId}
```

**边界场景**:
- date 为空校验失败
- description 为空校验失败
- date 为未来日期可能允许(视业务规则)

---

## CrashController

### 14. 触发异常以演示 SpringBoot 全局异常处理
- **接口路径**: `GET /oups`
- **方法名**: `triggerException`
- **返回类型**: `String`

**边界场景**:
- 该接口始终抛出异常

**错误码**:

| 码 | 说明 |
|----|------|
| 500 | 服务端内部错误(故意触发) |

---

## WelcomeController

### 15. 系统首页欢迎页面
- **接口路径**: `GET /`
- **方法名**: `welcome`
- **返回类型**: `String`

---

## VetController

### 16. 以 HTML 页面形式展示所有兽医列表
- **接口路径**: `GET /vets.html`
- **方法名**: `showVetList`
- **返回类型**: `String`

---

### 17. 以 JSON/XML 格式返回所有兽医列表数据
- **接口路径**: `GET /vets.json`
- **方法名**: `showResourcesVetList`
- **返回类型**: `Vets`

**响应示例**:
```json
{"vets":[{"id":1,"firstName":"James","lastName":"Carter","specialties":[]},{"id":2,"firstName":"Helen","lastName":"Leary","specialties":[{"name":"radiology"}]}]}
```

---

> AI生成