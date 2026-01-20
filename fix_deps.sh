#!/bin/bash
echo "修复Python依赖问题..."

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
source venv/bin/activate

# 备份旧的requirements.txt
cp requirements.txt requirements.txt.bak

# 创建修复后的requirements.txt
cat > requirements.txt << 'EOF'
Flask==2.3.3
Flask-CORS==4.0.0
Flask-SocketIO==5.3.4
paho-mqtt==1.6.1
waitress==2.1.2
python-dotenv==1.0.0
APScheduler==3.10.4
MarkupSafe==2.1.1
Werkzeug==2.3.7
Jinja2==3.1.2
EOF

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

echo "依赖修复完成！"
