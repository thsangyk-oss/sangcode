#!/bin/bash

# SangCode One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/thsangyk-oss/sangcode/main/install.sh | bash

set -e

echo -e "\n\033[1;34m===========================================\033[0m"
echo -e "\033[1;36m       SangCode Setup & Deployment\033[0m"
echo -e "\033[1;34m===========================================\033[0m\n"

# 1. Ask for configuration
read -p "Nhập mật khẩu truy cập cho SangCode (Mặc định: thanh-sang-123): " INPUT_PASS
SANGCODE_PASSWORD=${INPUT_PASS:-thanh-sang-123}

DOMAIN="sangcode.misanet.io.vn"
PORT="3003"
INSTALL_DIR="/opt/sangcode"

echo -e "\n\033[1;33m[1/5] Cài đặt các gói phụ thuộc (Dependencies)...\033[0m"
if [ -f /etc/debian_version ]; then
    apt-get update -qq
    apt-get install -y -qq git python3 python3-pip python3-venv tmux curl wget >/dev/null
elif [ -f /etc/redhat-release ]; then
    yum install -y -q git python3 python3-pip tmux curl wget >/dev/null
else
    echo "Hệ điều hành không được hỗ trợ cài tự động."
fi

echo -e "\033[1;33m[2/5] Kiểm tra và cài đặt ttyd...\033[0m"
if ! command -v ttyd &> /dev/null; then
    wget -q https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64 -O /usr/local/bin/ttyd
    chmod +x /usr/local/bin/ttyd
fi

echo -e "\033[1;33m[3/5] Tải Source Code từ GitHub...\033[0m"
if [ -d "$INSTALL_DIR" ]; then
    echo "Thư mục $INSTALL_DIR đã tồn tại. Đang cập nhật..."
    cd $INSTALL_DIR
    git reset --hard HEAD
    git pull origin main
else
    git clone https://github.com/thsangyk-oss/sangcode.git $INSTALL_DIR
    cd $INSTALL_DIR
fi

echo -e "\033[1;33m[4/5] Cài đặt môi trường Python (Virtual Environment)...\033[0m"
python3 -m venv venv
./venv/bin/pip install -q aiohttp

echo -e "\033[1;33m[5/5] Cấu hình và khởi động Systemd Service...\033[0m"
cat <<EOF > /etc/systemd/system/sangcode.service
[Unit]
Description=SangCode Web Terminal
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="SANGCODE_HOST=0.0.0.0"
Environment="SANGCODE_PORT=$PORT"
Environment="SANGCODE_PASSWORD=$SANGCODE_PASSWORD"
Environment="SANGCODE_WORKSPACE=/root"
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sangcode.service
systemctl restart sangcode.service

echo -e "\n\033[1;32m🎉 CÀI ĐẶT THÀNH CÔNG!\033[0m"
echo -e "--------------------------------------------------------"
echo -e "SangCode đang chạy ngầm trên port \033[1;36m$PORT\033[0m"
echo -e "Mật khẩu của bạn là: \033[1;31m$SANGCODE_PASSWORD\033[0m"
echo -e ""
echo -e "\033[1;35m>>> HƯỚNG DẪN PUBLISH RA DOMAIN ($DOMAIN) <<<\033[0m"
echo -e "Nếu bạn dùng Caddy làm Reverse Proxy, hãy thêm cấu hình sau vào \033[1mCaddyfile\033[0m:"
echo -e ""
echo -e "\033[1;36m$DOMAIN {\033[0m"
echo -e "\033[1;36m    reverse_proxy 127.0.0.1:$PORT\033[0m"
echo -e "\033[1;36m}\033[0m"
echo -e ""
echo -e "Sau đó chạy lệnh: \033[1m systemctl reload caddy \033[0m (hoặc docker exec caddy caddy reload)"
echo -e "--------------------------------------------------------\n"

