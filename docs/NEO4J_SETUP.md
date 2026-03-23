# Neo4j 安装与配置指南

## 方法一：Docker Desktop（推荐）

### 前提条件
- 安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- 启动 Docker Desktop

### 启动步骤

```bash
# 在项目根目录执行
docker compose up -d neo4j
```

### 验证安装

```bash
# 检查容器状态
docker ps | grep neo4j

# 访问 Neo4j Browser
# http://localhost:7474
# 用户名: neo4j
# 密码: aeropower_rag_2026
```

---

## 方法二：Windows 本地安装

### 下载与安装

1. 访问 [Neo4j Download Center](https://neo4j.com/download/)
2. 下载 **Neo4j 5 Community Edition** for Windows
3. 解压到目录，如 `C:\neo4j`

### 配置

1. 编辑 `conf/neo4j.conf`：

```conf
# 允许远程连接
dbms.default_listen_address=0.0.0.0

# 初始密码（首次启动后需修改）
dbms.security.auth_enabled=false
# 或设置默认密码
# dbms.security.auth_username=neo4j
# dbms.security.auth_password=aeropower_rag_2026
```

2. 启动 Neo4j：

```bash
# 使用 bin 目录下的命令
cd C:\neo4j\bin
.\neo4j.bat console
```

### 修改密码（如需要）

```bash
# 在首次启动后，使用以下命令修改密码
CALL dbms.security.changePassword('neo4j', 'new_password');
```

---

## 方法三：便携版（无需安装）

下载 Neo4j Portable 版本，解压即用。

---

## 数据导入

启动 Neo4j 后，运行导入脚本：

```bash
.venv/Scripts/python.exe scripts/load_graph_to_neo4j.py
```

---

## 故障排除

### 问题：端口7474/7687被占用

```conf
# 修改 neo4j.conf 使用其他端口
dbms.default_advertised_address=localhost:7688
dbms.connector.bolt.advertised_address=:7688
```

### 问题：Java 未安装

Neo4j 需要 Java 17+。下载安装 [Oracle JDK](https://www.oracle.com/java/technologies/downloads/) 或 [OpenJDK](https://adoptium.net/)。

### 问题：内存不足

```conf
# 调整 neo4j.conf 中的内存设置
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=512m
```

---

## 验证连接

运行此命令验证连接：

```bash
curl http://localhost:7474
```

应返回 Neo4j Browser 页面。
