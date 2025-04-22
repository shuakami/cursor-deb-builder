#!/bin/bash
set -e


DEBROOT="${APPNAME}-deb"
INSTALL_DIR="/opt/${APPNAME}"

echo "🔧 解压 AppImage ..."
chmod +x "$APPIMAGE"
./"$APPIMAGE" --appimage-extract > /dev/null

echo "📁 创建目录结构 ..."
rm -rf "$DEBROOT"
mkdir -p "$DEBROOT/DEBIAN"
mkdir -p "$DEBROOT/$INSTALL_DIR"
mkdir -p "$DEBROOT/usr/bin"
mkdir -p "$DEBROOT/usr/share/applications"
mkdir -p "$DEBROOT/usr/share/icons/hicolor/256x256/apps"

echo "📂 拷贝 AppImage 内容 ..."
cp -r squashfs-root/* "$DEBROOT/$INSTALL_DIR"

echo "🔗 创建可执行文件软链接 ..."
ln -sf "$INSTALL_DIR/AppRun" "$DEBROOT/usr/bin/$APPNAME"

echo "🖼️ 拷贝图标文件 ..."
ICON_PATH=$(find squashfs-root -type f -iname "*.png" | head -n 1)
if [[ -f "$ICON_PATH" ]]; then
    cp "$ICON_PATH" "$DEBROOT/usr/share/icons/hicolor/256x256/apps/${APPNAME}.png"
else
    echo "⚠️ 未找到图标文件，跳过图标处理"
fi

echo "📝 生成 desktop 文件 ..."
DESKTOP_FILE="$DEBROOT/usr/share/applications/${APPNAME}.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Cursor Editor
Comment=$DESCRIPTION
Exec=$APPNAME
Icon=${APPNAME}
Terminal=false
Type=Application
Categories=Utility;Development;Editor;
EOF

echo "📦 生成 control 文件 ..."
CONTROL_FILE="$DEBROOT/DEBIAN/control"
cat > "$CONTROL_FILE" <<EOF
Package: $APPNAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: libgtk-3-0, libnss3, libasound2
Maintainer: $MAINTAINER
Description: $DESCRIPTION
EOF

echo "🔐 设置权限 ..."
chmod 755 "$DEBROOT/DEBIAN"
chmod 644 "$CONTROL_FILE" "$DESKTOP_FILE"

echo "📦 开始打包 ..."
dpkg-deb --build "$DEBROOT"
FINAL_DEB="${APPNAME}-${VERSION}-${ARCH}.deb"
mv "${DEBROOT}.deb" "$FINAL_DEB"

echo "✅ 构建完成：$FINAL_DEB"

read -p "🚀 是否立即安装该 .deb？[y/N] " INSTALL_NOW
if [[ "$INSTALL_NOW" =~ ^[Yy]$ ]]; then
    sudo dpkg -i "$FINAL_DEB"
    echo "🎉 已安装 $APPNAME"
else
    echo "💡 可手动安装：sudo dpkg -i $FINAL_DEB"
fi

