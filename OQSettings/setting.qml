import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 1000
    height: 700

    // 添加信号
    signal backToMain()

    // 统一颜色定义
    readonly property color primaryTextColor: "#ffffff"
    readonly property color secondaryTextColor: "#e0e0e0"
    readonly property color hintTextColor: "#aaaaaa"
    readonly property color accentTextColor: "#6c9eff"
    readonly property color successTextColor: "#44ff44"
    readonly property color disabledTextColor: "#666666"



    // 背景渐变 - 使用纯QML实现
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#1e1e2e" }
            GradientStop { position: 1.0; color: "#0f0f1a" }
        }
    }

    // 标题栏
    Rectangle {
        id: header
        width: parent.width
        height: 80

        // 标题栏渐变背景
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#2a2a4a" }
            GradientStop { position: 1.0; color: "#1a1a2a" }
        }

        Text {
            text: qsTr("系统设置")
            font.pixelSize: 28
            font.bold: true
            color: root.primaryTextColor
            anchors.centerIn: parent
            font.family: "Microsoft YaHei"
        }

        // // 使用矩形代替图标
        // Rectangle {
        //     width: 40
        //     height: 40
        //     radius: 8
        //     color: "#6c9eff"
        //     anchors.left: parent.left
        //     anchors.leftMargin: 30
        //     anchors.verticalCenter: parent.verticalCenter
        //
        //     Text {
        //         text: "⚙"
        //         color: root.primaryTextColor
        //         font.pixelSize: 24
        //         anchors.centerIn: parent
        //     }
        // }

        // 返回按钮
        Rectangle {
            width: 40
            height: 40
            radius: 8
            color: "#ff6b6b"
            anchors.right: parent.right
            anchors.rightMargin: 30
            anchors.verticalCenter: parent.verticalCenter

            Text {
                text: "←"
                color: root.primaryTextColor
                font.pixelSize: 24
                anchors.centerIn: parent
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    // 通过信号返回主页面
                    root.backToMain()
                }
            }
        }
    }

    // 主内容区
    Rectangle {
        id: contentArea
        width: parent.width - 40
        height: parent.height - header.height - footer.height - 40
        anchors.top: header.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 20
        color: "#202036"
        radius: 12

        // 使用边框实现阴影效果
        border {
            width: 1
            color: "#4c4c7a"
        }

        // 选项卡控件
        TabBar {
            id: tabBar
            width: parent.width
            height: 60
            currentIndex: 0 // 设置默认索引
            position: TabBar.Header
            spacing: 0

            background: Rectangle {
                color: "transparent"
            }

            Repeater {
                model: ["系统配置", "界面设置", "ASR设置", "助理设置"]

                TabButton {
                    id: tabButton
                    text: modelData
                    width: implicitWidth + 40
                    height: parent.height

                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: 16
                        font.family: "Microsoft YaHei"
                        color: primaryTextColor
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        color: parent.checked ? "#4c4c7a" : "transparent"
                        radius: 6
                        anchors.fill: parent
                        anchors.margins: 8
                    }
                }
            }
        }

        SwipeView {
            id: swipeView
            width: parent.width
            height: contentArea.height - tabBar.height
            anchors.top: tabBar.bottom
            currentIndex: tabBar.currentIndex
            clip: true
            interactive: false

            // 系统配置页面 - 修正布局
            ScrollView {
                id: systemTab
                clip: true
                contentWidth: systemColumn.width
                contentHeight: systemColumn.height

                ColumnLayout {
                    id: systemColumn
                    width: swipeView.width
                    spacing: 20

                    // 窗口样式设置
                    GroupBox {
                        title: qsTr("窗口样式")
                        Layout.fillWidth: true
                        Layout.leftMargin: 20
                        Layout.rightMargin: 20
                        topPadding: 40
                        padding: 20
                        label: Label {
                            text: parent.title
                            color: root.accentTextColor
                            font.pixelSize: 18
                            font.bold: true
                            font.family: "Microsoft YaHei"
                            leftPadding: 10
                        }
                        background: Rectangle {
                            color: "#25253e"
                            radius: 10
                            border.color: "#4c4c7a"
                        }

                        ColumnLayout {
                            width: parent.width
                            spacing: 15

                            RowLayout {
                                Label {
                                    text: qsTr("显示模式:")
                                    color: root.primaryTextColor
                                    Layout.preferredWidth: 120
                                    font.family: "Microsoft YaHei"
                                }
                                ComboBox {
                                    id: windowModeComboBox
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 45
                                    Layout.minimumHeight: 40
                                    model: ["沉浸模式", "窗口模式", "桌宠模式"]
                                    font.family: "Microsoft YaHei"
                                    font.pixelSize: 14
                                    contentItem: Text {
                                        text: parent.displayText
                                        font: parent.font
                                        color: root.primaryTextColor
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: 10
                                    }
                                    background: Rectangle {
                                        radius: 6
                                        color: "#3a3a5a"
                                        border.width: 1
                                        border.color: "#4c4c7a"
                                    }
                                    onCurrentIndexChanged: {
                                        // 当选择改变时通知槽函数
                                        settingsSlot.onWindowModeChanged(currentIndex)
                                    }
                                }
                            }

                            // 模式说明
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 80
                                color: "#1a1a2a"
                                radius: 6
                                border.width: 1
                                border.color: "#3a3a5a"

                                Text {
                                    id: modeDescription
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    color: root.secondaryTextColor
                                    font.family: "Microsoft YaHei"
                                    font.pixelSize: 12
                                    wrapMode: Text.WordWrap
                                    verticalAlignment: Text.AlignVCenter
                                    text: {
                                        switch(windowModeComboBox.currentIndex) {
                                            case 0: return "沉浸模式：全屏显示，隐藏标题栏和边框，提供最佳的沉浸体验"
                                            case 1: return "窗口模式：标准窗口显示，可自由调整大小和位置，适合多任务操作"
                                            case 2: return "桌宠模式：小窗口悬浮显示，始终置顶，不干扰其他应用程序"
                                            default: return ""
                                        }
                                    }
                                }
                            }

                            Button {
                                text: qsTr("保存")
                                Layout.alignment: Qt.AlignRight
                                background: Rectangle {
                                    radius: 6
                                    color: parent.down ? "#4c7ce0" : "#6c9eff"
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    // 调用槽函数保存窗口设置
                                    settingsSlot.onWindowModeChanged(windowModeComboBox.currentIndex)
                                    settingsSlot.onSaveWindowSettings()
                                }
                            }
                        }
                    }


                }
            }

            // 界面设置页面
            ScrollView {
                id: interfaceTab
                clip: true
                contentWidth: interfaceColumn.width
                contentHeight: interfaceColumn.height

                ColumnLayout {
                    id: interfaceColumn
                    width: swipeView.width
                    spacing: 20

                    // 角色设置
                    GroupBox {
                        title: qsTr("角色设置")
                        Layout.fillWidth: true
                        Layout.leftMargin: 20
                        Layout.rightMargin: 20
                        topPadding: 40
                        padding: 20
                        label: Label {
                            text: parent.title
                            color: "#6c9eff"
                            font.pixelSize: 18
                            font.bold: true
                            font.family: "Microsoft YaHei"
                            leftPadding: 10
                        }
                        background: Rectangle {
                            color: "#25253e"
                            radius: 10
                            border.color: "#4c4c7a"
                        }

                        ColumnLayout {
                            width: parent.width
                            spacing: 15

                            RowLayout {
                                Label {
                                    text: qsTr("选择模型文件:")
                                    color: root.primaryTextColor
                                    Layout.preferredWidth: 120
                                    font.family: "Microsoft YaHei"
                                }
                                TextField {
                                    id: rolePathField
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("选择模型文件...")
                                    placeholderTextColor: root.secondaryTextColor
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                    readOnly: true
                                    background: Rectangle {
                                        radius: 4
                                        color: "#3a3a5a"
                                        border.width: 1
                                        border.color: "#4c4c7a"
                                    } 
                                    onTextChanged: {
                                        if (text.length > 0) {
                                            settingsSlot.onModelPathChanged(text)
                                        }
                                    }
                                }
                                Button {
                                    text: qsTr("浏览")
                                    background: Rectangle {
                                        radius: 6
                                        color: parent.down ? "#5a5a8a" : "#7a7aaa"
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: root.primaryTextColor
                                        font.family: "Microsoft YaHei"
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: {
                                        // 调用槽函数浏览模型文件
                                        var filePath = settingsSlot.onBrowseModelFile()
                                        if (filePath) {
                                            rolePathField.text = filePath
                                            settingsSlot.onModelPathChanged(filePath)
                                        }
                                    }
                                }
                            }

                            Button {
                                text: qsTr("保存")
                                Layout.alignment: Qt.AlignRight
                                background: Rectangle {
                                    radius: 6
                                    color: parent.down ? "#4c7ce0" : "#6c9eff"
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    // 调用槽函数保存模型设置
                                    settingsSlot.onSaveModelSettings()
                                }
                            }
                        }
                    }

                    // 背景设置
                    GroupBox {
                        title: qsTr("背景设置")
                        Layout.fillWidth: true
                        Layout.leftMargin: 20
                        Layout.rightMargin: 20
                        topPadding: 40
                        padding: 20
                        label: Label {
                            text: parent.title
                            color: "#6c9eff"
                            font.pixelSize: 18
                            font.bold: true
                            font.family: "Microsoft YaHei"
                            leftPadding: 10
                        }
                        background: Rectangle {
                            color: "#25253e"
                            radius: 10
                            border.color: "#4c4c7a"
                        }

                        ColumnLayout {
                            width: parent.width
                            spacing: 15

                            RowLayout {
                                Label {
                                    text: qsTr("背景类型:")
                                    color: root.primaryTextColor
                                    Layout.preferredWidth: 120
                                    font.family: "Microsoft YaHei"
                                }
                                ComboBox {
                                    id: backgroundTypeComboBox
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 45
                                    Layout.minimumHeight: 40
                                    model: ["默认壁纸", "自定义壁纸"]
                                    font.family: "Microsoft YaHei"
                                    font.pixelSize: 14
                                    contentItem: Text {
                                        text: parent.displayText
                                        font: parent.font
                                        color: root.primaryTextColor
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: 10
                                    }
                                    background: Rectangle {
                                        radius: 6
                                        color: "#3a3a5a"
                                        border.width: 1
                                        border.color: "#4c4c7a"
                                    }
                                    onCurrentIndexChanged: {
        settingsSlot.onBackgroundTypeChanged(currentIndex)
    }
                                }
                            }

                            // 默认壁纸时显示背景主题选择
                            RowLayout {
                                visible: backgroundTypeComboBox.currentIndex === 0
                                Label {
                                    text: qsTr("背景主题:")
                                    color: root.primaryTextColor
                                    Layout.preferredWidth: 120
                                    font.family: "Microsoft YaHei"
                                }
                                ComboBox {
                                    id: backgroundThemeComboBox
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 45
                                    Layout.minimumHeight: 40
                                    model: ["默认背景", "深色主题", "月亮主题", "科技寝室", "绿色自然", "城市房间", "教室场景", "室内场景", "山谷风景"]
                                    font.family: "Microsoft YaHei"
                                    font.pixelSize: 14
                                    contentItem: Text {
                                        text: parent.displayText
                                        font: parent.font
                                        color: root.primaryTextColor
                                        verticalAlignment: Text.AlignVCenter
                                        leftPadding: 10
                                    }
                                    background: Rectangle {
                                        radius: 6
                                        color: "#3a3a5a"
                                        border.width: 1
                                        border.color: "#4c4c7a"
                                    }
                                    onCurrentIndexChanged: {
        settingsSlot.onBackgroundThemeChanged(currentIndex)
    }
                                }
                            }

                            // 自定义壁纸选择区域（仅在选择自定义壁纸时显示）
                            RowLayout {
                                visible: backgroundTypeComboBox.currentIndex === 1
                                Label {
                                    text: qsTr("壁纸路径:")
                                    color: root.primaryTextColor
                                    Layout.preferredWidth: 120
                                    font.family: "Microsoft YaHei"
                                }
                                TextField {
                                    id: wallpaperPathField
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("选择壁纸文件...")
                                    placeholderTextColor: root.secondaryTextColor
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                    readOnly: true
                                    background: Rectangle {
                                        radius: 4
                                        color: "#3a3a5a"
                                        border.width: 1
                                        border.color: "#4c4c7a"
                                    }
                                    onTextChanged: {
                                        if (text.length > 0) {
                                            settingsSlot.onWallpaperPathChanged(text)
                                        }
                                    }
                                }
                                Button {
                                    text: qsTr("浏览")
                                    background: Rectangle {
                                        radius: 6
                                        color: parent.down ? "#5a5a8a" : "#7a7aaa"
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: root.primaryTextColor
                                        font.family: "Microsoft YaHei"
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: {
                                        // 调用槽函数浏览壁纸文件
                                        var filePath = settingsSlot.onBrowseWallpaper()
                                        if (filePath) {
                                            wallpaperPathField.text = filePath
                                            settingsSlot.onWallpaperPathChanged(filePath)
                                        }
                                    }
                                }
                            }

                            Button {
                                text: qsTr("保存")
                                Layout.alignment: Qt.AlignRight
                                background: Rectangle {
                                    radius: 6
                                    color: parent.down ? "#4c7ce0" : "#6c9eff"
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    settingsSlot.onSaveBackgroundSettings()
                                }
                            }
                        }
                    }

                }
            }

            // ASR设置页面
            ScrollView {
                id: asrTab
                clip: true
                contentWidth: asrColumn.width
                contentHeight: asrColumn.height

                ColumnLayout {
                    id: asrColumn
                    width: swipeView.width
                    spacing: 20

                    // 麦克风设置
                    GroupBox {
                        title: qsTr("麦克风设置")
                        Layout.fillWidth: true
                        Layout.leftMargin: 20
                        Layout.rightMargin: 20
                        topPadding: 40
                        padding: 20
                        label: Label {
                            text: parent.title
                            color: "#6c9eff"
                            font.pixelSize: 18
                            font.bold: true
                            font.family: "Microsoft YaHei"
                            leftPadding: 10
                        }
                        background: Rectangle {
                            color: "#25253e"
                            radius: 10
                            border.color: "#4c4c7a"
                        }

                        ColumnLayout {
                            width: parent.width
                            spacing: 15

                            CheckBox {
                                id: interruptAi
                                text: qsTr("允许AI说话被打断")
                                checked: false
                                enabled: false
                                font.family: "Microsoft YaHei"
                                contentItem: Text {
                                    text: parent.text
                                    color: root.disabledTextColor
                                    font.family: "Microsoft YaHei"
                                    leftPadding: parent.indicator.width + parent.spacing
                                }
                                onCheckedChanged: {
                                    // 功能暂时禁用，不执行任何操作
                                }
                            }
                        }
                    }

                    // 麦克风测试
                    GroupBox {
                        title: qsTr("麦克风测试")
                        Layout.fillWidth: true
                        Layout.leftMargin: 20
                        Layout.rightMargin: 20
                        topPadding: 40
                        padding: 20
                        label: Label {
                            text: parent.title
                            color: "#6c9eff"
                            font.pixelSize: 18
                            font.bold: true
                            font.family: "Microsoft YaHei"
                            leftPadding: 10
                        }
                        background: Rectangle {
                            color: "#25253e"
                            radius: 10
                            border.color: "#4c4c7a"
                        }

                        ColumnLayout {
                            width: parent.width
                            spacing: 20

                            RowLayout {
                                Label {
                                    text: qsTr("麦克风灵敏度:")
                                    color: root.primaryTextColor
                                    Layout.preferredWidth: 120
                                    font.family: "Microsoft YaHei"
                                }

                                Slider {
                                    id: micSensitivity
                                    Layout.fillWidth: true
                                    value: 0.7
                                    background: Rectangle {
                                        x: parent.leftPadding
                                        y: parent.topPadding + parent.availableHeight / 2 - height / 2
                                        implicitWidth: 200
                                        implicitHeight: 6
                                        width: parent.availableWidth
                                        height: implicitHeight
                                        radius: 3
                                        color: "#4c4c7a"

                                        Rectangle {
                                            width: parent.width * micSensitivity.visualPosition
                                            height: parent.height
                                            color: "#6c9eff"
                                            radius: 3
                                        }
                                    }

                                    handle: Rectangle {
                                        x: micSensitivity.leftPadding + micSensitivity.visualPosition * (micSensitivity.availableWidth - width)
                                        y: micSensitivity.topPadding + micSensitivity.availableHeight / 2 - height / 2
                                        implicitWidth: 22
                                        implicitHeight: 22
                                        radius: 11
                                        color: micSensitivity.pressed ? "#ffffff" : "#f0f0f0"
                                        border.color: "#6c9eff"
                                        border.width: 2
                                    }
                                    onValueChanged: {
                                        settingsSlot.onMicSensitivityChanged(value)
                                    }
                                }
                            }

                            RowLayout {
                                Label {
                                    text: qsTr("当前状态:")
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                }

                                Rectangle {
                                    width: 20
                                    height: 20
                                    radius: 10
                                    color: root.successTextColor
                                }

                                Label {
                                    text: qsTr("正常")
                                    color: root.successTextColor
                                    font.family: "Microsoft YaHei"
                                }

                                Item {
                                    Layout.fillWidth: true
                                }

                                Button {
                                    text: qsTr("测试麦克风")
                                    background: Rectangle {
                                        radius: 6
                                        color: parent.down ? "#4c7ce0" : "#6c9eff"
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: root.primaryTextColor
                                        font.family: "Microsoft YaHei"
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: {
                                        settingsSlot.onTestMicrophone()
                                    }
                                }
                            }
                        }
                    }
                }
            }



            // 助理设置页面
            ScrollView {
                id: assistantTab
                clip: true
                contentWidth: assistantColumn.width
                contentHeight: assistantColumn.height

                ColumnLayout {
                    id: assistantColumn
                    width: swipeView.width
                    spacing: 20

                    // 自动回复设置
                    GroupBox {
                        title: qsTr("自动回复设置")
                        Layout.fillWidth: true
                        Layout.leftMargin: 20
                        Layout.rightMargin: 20
                        topPadding: 40
                        padding: 20
                        label: Label {
                            text: parent.title
                            color: "#6c9eff"
                            font.pixelSize: 18
                            font.bold: true
                            font.family: "Microsoft YaHei"
                            leftPadding: 10
                        }
                        background: Rectangle {
                            color: "#25253e"
                            radius: 10
                            border.color: "#4c4c7a"
                        }

                        ColumnLayout {
                            width: parent.width
                            spacing: 15

                            CheckBox {
                                id: autoReply
                                text: qsTr("允许助理自动说话")
                                checked: true
                                font.family: "Microsoft YaHei"
                                contentItem: Text {
                                    text: parent.text
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                    leftPadding: parent.indicator.width + parent.spacing
                                }
                                onCheckedChanged: {
                                    settingsSlot.onAutoReplyChanged(checked)
                                }
                            }

                            RowLayout {
                                visible: autoReply.checked
                                Label {
                                    text: qsTr("回复延迟:")
                                    color: root.primaryTextColor
                                    Layout.preferredWidth: 120
                                    font.family: "Microsoft YaHei"
                                }
                                SpinBox {
                                    id: replyDelay
                                    from: 0
                                    to: 10
                                    value: 2
                                    editable: true
                                    font.family: "Microsoft YaHei"
                                    background: Rectangle {
                                        radius: 4
                                        color: "#3a3a5a"
                                        border.width: 1
                                        border.color: "#4c4c7a"
                                    }
                                    contentItem: TextInput {
                                        color: root.primaryTextColor
                                        text: parent.value
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        readOnly: !parent.editable
                                        validator: parent.validator
                                        font.family: "Microsoft YaHei"
                                    }
                                    onValueChanged: {
                                        settingsSlot.onReplyDelayChanged(value)
                                    }
                                }
                                Label {
                                    text: qsTr("秒")
                                    color: root.primaryTextColor
                                    font.family: "Microsoft YaHei"
                                }
                            }
                        }
                    }

                    

                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        Layout.rightMargin: 20
                        spacing: 10


                        Button {
                            text: qsTr("保存")
                            background: Rectangle {
                                radius: 6
                                color: parent.down ? "#4c7ce0" : "#6c9eff"
                            }
                            contentItem: Text {
                                text: parent.text
                                color: root.primaryTextColor
                                font.family: "Microsoft YaHei"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            onClicked: {
                                settingsSlot.onSaveAssistantSettings()
                            }
                        }
                    }
                }
            }
        }
    }

    // 状态栏
    Rectangle {
        id: footer
        width: parent.width
        height: 30
        anchors.bottom: parent.bottom
        color: "#151522"

        Text {
            text: qsTr("设置页面 | © OPEN-LLM-VTUBE-PYQT")
            color: root.primaryTextColor
            font.pixelSize: 12
            font.family: "Microsoft YaHei"
            anchors.left: parent.left
            anchors.leftMargin: 20
            anchors.verticalCenter: parent.verticalCenter
        }

        // 修复：安全访问currentItem.text
        Text {
            text: {
                if (tabBar.currentItem) {
                    return qsTr("当前选项卡: ") + tabBar.currentItem.text
                }
                return qsTr("当前选项卡: 无")
            }
            color: root.primaryTextColor
            font.pixelSize: 12
            font.family: "Microsoft YaHei"
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
