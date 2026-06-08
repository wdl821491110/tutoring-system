# 课消管理系统 - 微信小程序部署指南

## 个人主体合规要点

1. **推荐类目**：选择「**工具 > 信息查询**」，这是个人主体最容易通过的类目
2. **禁止功能**：❌ 在线支付、❌ 用户间社交互动、❌ 内容社区/论坛
3. **必须项**：✅ 隐私政策页面、✅ 所有页面有实际内容、✅ 功能完整无空白页
4. **注意事项**：小程序描述中强调「机构内部管理工具」，避免使用「在线教育」「课程销售」等敏感词汇

## ⭐ 推荐方案：CloudBase 云开发（免费额度）

腾讯云 CloudBase 为微信小程序提供**免费额度**：
- 1GB 云数据库存储
- 5GB 静态托管
- 2GB 云函数流量/月
- 适合小规模使用，**基本免费**

### 步骤1：开通 CloudBase
1. 打开 [CloudBase 控制台](https://console.cloud.tencent.com/tcb)
2. 创建环境（选择「按量计费」- 免费额度内不收费）
3. 记录 **环境 ID**

### 步骤2：部署后端到云托管
```bash
# 1. 在项目目录创建 Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY app.py database.py requirements.txt run.py ./
COPY templates/ templates/
COPY static/ static/
RUN pip install -r requirements.txt -i https://mirrors.tencent.com/pypi/simple/
RUN mkdir -p data
EXPOSE 5000
CMD ["python", "app.py"]
EOF

# 2. 使用 CloudBase CLI 部署
npm install -g @cloudbase/cli
tcb login
tcb hosting deploy ./ -e 你的环境ID
```

### 步骤3：配置小程序服务器域名
在微信公众平台「开发管理 → 服务器域名」中：
- request合法域名：`https://你的环境ID.service.tcloudbase.com`
- 注意：**必须是 HTTPS**

### 步骤4：修改小程序配置
修改 `miniprogram/app.js`：
```javascript
const BASE_URL = 'https://你的环境ID.service.tcloudbase.com';
```

## 备选方案：轻量应用服务器

如果 CloudBase 不够用，推荐腾讯云轻量应用服务器：
- 最低配置：2核2G，约 ¥50/月
- 安装 Nginx + SSL 证书（Let's Encrypt 免费）
- 使用 waitress 运行 Flask

```bash
# 服务器上操作
pip install flask waitress
nohup waitress-serve --host=0.0.0.0 --port=5000 app:app &

# Nginx 配置
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
    }
}
```

## 本地测试方案（免费）

在正式部署前，可以用 ngrok 做本地穿透测试：

```bash
# 1. 下载 ngrok: https://ngrok.com
# 2. 启动本地服务
python app.py

# 3. 创建隧道
ngrok http 5000

# 4. 将 ngrok 提供的 https://xxx.ngrok.io 填入 app.js 的 BASE_URL
```

## 审核提交流程

1. 在微信开发者工具中，点击「上传」→ 填写版本号和备注
2. 登录 [微信公众平台](https://mp.weixin.qq.com)
3. 进入「版本管理」→ 选择刚上传的版本 →「提交审核」
4. 配置信息：
   - **类目**：工具 > 信息查询
   - **标签**：教育管理、课时管理
   - **功能**：数据查询、信息展示
5. 等待审核（通常1-3个工作日）

## 常见审核拒绝原因

| 原因 | 解决方法 |
|------|----------|
| 服务类目不匹配 | 改用「工具>信息查询」 |
| 功能不完整 | 确保所有tab页面有内容，没有空白页 |
| 缺少隐私政策 | 添加隐私政策页面 |
| 含有支付功能 | 个人主体不能有支付，移除相关代码 |
| 用户生成内容 | 移除评论/发帖/上传等功能 |
