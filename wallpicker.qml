// khoiprOS — bảng chọn hình nền (Super+W), chạy bằng quickshell (Qt Quick, vẽ bằng card đồ hoạ → mượt).
// main.py mở bảng này và truyền cổng / mã API / ngôn ngữ / màu nhấn qua biến môi trường.
// Ảnh xem trước lấy từ máy chủ nội bộ của khoiprOS (đã làm sẵn, lưu đệm).
import QtQuick
import Quickshell
import Quickshell.Wayland

ShellRoot {
    id: root
    readonly property string port: Quickshell.env("KHOIPROS_PORT") || "8888"
    readonly property string token: Quickshell.env("KHOIPROS_TOKEN") || ""
    readonly property bool en: (Quickshell.env("KHOIPROS_LANG") || "vi") === "en"
    readonly property color accent: Quickshell.env("KHOIPROS_ACCENT") || "#70a1ff"
    readonly property string api: "http://127.0.0.1:" + port
    property var all: []
    property bool closing: false

    function tr(vi, enText) { return en ? enText : vi }

    function request(method, path, body, cb) {
        const x = new XMLHttpRequest()
        x.onreadystatechange = function () {
            if (x.readyState === XMLHttpRequest.DONE && cb) {
                let j = null
                try { j = JSON.parse(x.responseText) } catch (e) {}
                cb(j)
            }
        }
        x.open(method, api + path)
        x.setRequestHeader("X-KKK-Token", token)
        if (body) x.setRequestHeader("Content-Type", "application/json")
        x.send(body ? JSON.stringify(body) : null)
    }

    function rebuild(q) {
        wallModel.clear()
        let start = 0
        for (let k = 0; k < all.length; k++) {
            const it = all[k]
            if (q && it.name.toLowerCase().indexOf(q) < 0) continue
            if (it.cur && !q) start = wallModel.count
            wallModel.append({ idx: it.i, name: it.name, dir: it.dir || "", w: it.w || 0, h: it.h || 0, mb: it.mb || 0, ext: it.ext || "", cur: !!it.cur })
        }
        view.currentIndex = start
        view.positionViewAtIndex(start, PathView.Center)
    }

    function quit() {
        if (closing) return
        closing = true
        fadeOut.start()
    }

    function apply() {
        if (closing || wallModel.count === 0) return
        const it = wallModel.get(view.currentIndex)
        request("POST", "/api/cmd", { type: "setwall", i: it.idx, fx: true }, null)
        quit()
    }

    function sig(a) { return a.map(x => x.i + ":" + x.name).join("|") }

    Component.onCompleted: {
        // danh sách main.py quét sẵn → hiện ngay lập tức
        let pre = null
        try { pre = JSON.parse(Quickshell.env("KHOIPROS_WALLS") || "null") } catch (e) {}
        if (pre && pre.length) {
            root.all = pre
            rebuild("")
            loading.visible = false
        }
        // rồi hỏi lại máy chủ ở nền sau — chỉ vẽ lại nếu thư mục có ảnh mới / bớt ảnh
        request("GET", "/api/wallpapers", null, function (j) {
            const fresh = (j && j.items) ? j.items : []
            loading.visible = false
            if (pre && pre.length && sig(fresh) === sig(root.all)) return
            const keep = wallModel.count > 0 && view.currentIndex >= 0 ? wallModel.get(view.currentIndex).name : ""
            root.all = fresh
            rebuild(search.text.trim().toLowerCase())
            if (keep) for (let k = 0; k < wallModel.count; k++)
                if (wallModel.get(k).name === keep) { view.currentIndex = k; break }
        })
    }

    ListModel { id: wallModel }

    PanelWindow {
        id: win
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
        WlrLayershell.namespace: "khoipros-wallpaper"

        Item {
            id: stage
            anchors.fill: parent
            opacity: 0
            focus: true
            Component.onCompleted: { fadeIn.start(); stage.forceActiveFocus() }
            NumberAnimation { id: fadeIn; target: stage; property: "opacity"; to: 1; duration: 200; easing.type: Easing.OutCubic }
            NumberAnimation { id: fadeOut; target: stage; property: "opacity"; to: 0; duration: 180; easing.type: Easing.InCubic; onFinished: Qt.quit() }

            // nền trong suốt: chỉ tối dần quanh dải ảnh + ánh màu nhấn
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#26040610" }
                    GradientStop { position: 0.38; color: "#8c04060c" }
                    GradientStop { position: 0.62; color: "#b304060c" }
                    GradientStop { position: 1.0; color: "#33040610" }
                }
            }
            Rectangle {
                width: parent.width * 0.9; height: parent.height * 0.5
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height * 0.36
                radius: height / 2
                color: root.accent
                opacity: 0.12
            }

            // thứ · ngày · giờ
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height * 0.06
                spacing: 4
                Text {
                    id: dayText
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: "white"; font.pixelSize: 54; font.weight: Font.ExtraLight; font.letterSpacing: 10
                    font.capitalization: Font.AllUppercase
                }
                Text {
                    id: dateText
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: "#c8ffffff"; font.pixelSize: 13; font.letterSpacing: 4; font.capitalization: Font.AllUppercase
                }
                Text {
                    id: timeText
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: "#8cffffff"; font.pixelSize: 12; font.letterSpacing: 3
                }
                Item { width: 1; height: 8 }
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 300; height: 34; radius: 11
                    color: "#8c0a0e18"; border.color: search.activeFocus ? root.accent : "#26ffffff"; border.width: 1
                    Text {
                        anchors.verticalCenter: parent.verticalCenter; x: 14
                        text: "⌕"; color: "#99ffffff"; font.pixelSize: 15
                    }
                    TextInput {
                        id: search
                        anchors.verticalCenter: parent.verticalCenter
                        x: 36; width: parent.width - 50
                        color: "white"; font.pixelSize: 13; clip: true
                        selectByMouse: true
                        onTextChanged: root.rebuild(text.trim().toLowerCase())
                        Keys.onLeftPressed: view.decrementCurrentIndex()
                        Keys.onRightPressed: view.incrementCurrentIndex()
                        Keys.onReturnPressed: root.apply()
                        Keys.onEscapePressed: { if (text) text = ""; else root.quit() }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: !search.text
                            text: root.tr("Tìm hình nền…", "Search wallpapers…")
                            color: "#73ffffff"; font.pixelSize: 13
                        }
                    }
                }
            }
            Timer {
                interval: 10000; running: true; repeat: true; triggeredOnStart: true
                onTriggered: {
                    const d = new Date()
                    const vi = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"]
                    const e = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                    const mon = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                    dayText.text = root.en ? e[d.getDay()] : vi[d.getDay()]
                    dateText.text = root.en ? (d.getDate() + " " + mon[d.getMonth()] + " " + d.getFullYear())
                                            : (d.getDate() + " tháng " + (d.getMonth() + 1) + ", " + d.getFullYear())
                    timeText.text = "· " + Qt.formatTime(d, root.en ? "hh:mm AP" : "HH:mm") + " ·"
                }
            }

            // dải ảnh: ảnh giữa thẳng mặt, hai bên nghiêng 3D quay vào giữa
            PathView {
                id: view
                anchors.left: parent.left; anchors.right: parent.right
                y: parent.height * 0.55 - height / 2
                height: 330
                model: wallModel
                pathItemCount: Math.min(wallModel.count, 13)
                preferredHighlightBegin: 0.5
                preferredHighlightEnd: 0.5
                highlightRangeMode: PathView.StrictlyEnforceRange
                highlightMoveDuration: 300
                snapMode: PathView.SnapOneItem
                interactive: true
                cacheItemCount: 4

                path: Path {
                    startX: -150; startY: view.height / 2
                    PathAttribute { name: "rot"; value: 58 }
                    PathAttribute { name: "sc"; value: 0.78 }
                    PathAttribute { name: "zz"; value: 0 }
                    PathAttribute { name: "dim"; value: 0.55 }
                    PathLine { x: view.width / 2 - 230; y: view.height / 2 }
                    PathAttribute { name: "rot"; value: 50 }
                    PathAttribute { name: "sc"; value: 0.86 }
                    PathAttribute { name: "zz"; value: 50 }
                    PathAttribute { name: "dim"; value: 0.32 }
                    PathLine { x: view.width / 2; y: view.height / 2 }
                    PathAttribute { name: "rot"; value: 0 }
                    PathAttribute { name: "sc"; value: 1.4 }
                    PathAttribute { name: "zz"; value: 100 }
                    PathAttribute { name: "dim"; value: 0 }
                    PathLine { x: view.width / 2 + 230; y: view.height / 2 }
                    PathAttribute { name: "rot"; value: -50 }
                    PathAttribute { name: "sc"; value: 0.86 }
                    PathAttribute { name: "zz"; value: 50 }
                    PathAttribute { name: "dim"; value: 0.32 }
                    PathLine { x: view.width + 150; y: view.height / 2 }
                    PathAttribute { name: "rot"; value: -58 }
                    PathAttribute { name: "sc"; value: 0.78 }
                    PathAttribute { name: "zz"; value: 0 }
                    PathAttribute { name: "dim"; value: 0.55 }
                }

                delegate: Item {
                    id: card
                    required property int index
                    required property int idx
                    required property bool cur
                    width: 300; height: 169
                    z: PathView.zz
                    scale: PathView.sc
                    property real dimv: PathView.dim
                    readonly property bool isCur: PathView.isCurrentItem
                    transform: Rotation { origin.x: card.width / 2; origin.y: card.height / 2; axis { x: 0; y: 1; z: 0 } angle: card.PathView.rot }

                    Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 4; color: card.isCur ? root.accent : "transparent" }
                    Rectangle { anchors.fill: parent; color: "#0b0f1a" }
                    Image {
                        anchors.fill: parent
                        source: root.api + "/api/wpthumb?i=" + card.idx
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        smooth: true
                        sourceSize.width: 640
                    }
                    Rectangle { anchors.fill: parent; color: "black"; opacity: card.dimv }
                    Rectangle {
                        visible: card.cur
                        x: 8; y: 7; height: 18; radius: 9; width: nowText.width + 14
                        color: root.accent
                        Text { id: nowText; anchors.centerIn: parent; text: root.tr("Đang dùng", "Current"); color: "white"; font.pixelSize: 10; font.bold: true }
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { if (card.isCur) root.apply(); else view.currentIndex = card.index }
                    }
                }
            }

            // thông tin ảnh đang chọn
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height * 0.55 + 140
                spacing: 6
                visible: wallModel.count > 0
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    readonly property var it: wallModel.count > 0 && view.currentIndex >= 0 ? wallModel.get(view.currentIndex) : null
                    text: it ? it.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ") : ""
                    color: "white"; font.pixelSize: 14; font.weight: Font.DemiBold
                    elide: Text.ElideMiddle; width: Math.min(implicitWidth, win.width * 0.7)
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    readonly property var it: wallModel.count > 0 && view.currentIndex >= 0 ? wallModel.get(view.currentIndex) : null
                    text: it ? [it.w && it.h ? it.w + " × " + it.h : "", it.mb ? it.mb + " MB" : "", it.ext, it.dir, (view.currentIndex + 1) + " / " + wallModel.count].filter(s => s).join("    ") : ""
                    color: "#99ffffff"; font.pixelSize: 12; font.letterSpacing: 0.4
                }
            }

            Text {
                id: loading
                anchors.centerIn: parent
                text: root.tr("Đang tìm hình nền…", "Looking for wallpapers…")
                color: "#b3ffffff"; font.pixelSize: 14
            }
            Text {
                anchors.centerIn: parent
                visible: !loading.visible && wallModel.count === 0
                horizontalAlignment: Text.AlignHCenter
                text: search.text ? root.tr("Không có ảnh nào khớp", "No matching images")
                                  : root.tr("Chưa có ảnh nào.\nBỏ ảnh vào ~/Pictures/khoipros rồi mở lại (Super+W).",
                                            "No images yet.\nPut images in ~/Pictures/khoipros and open this again (Super+W).")
                color: "#bfffffff"; font.pixelSize: 14
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom; anchors.bottomMargin: parent.height * 0.035
                spacing: 22
                Repeater {
                    model: [["← →", root.tr("lướt", "browse")], ["Enter", root.tr("đặt làm hình nền", "set as wallpaper")], ["Esc", root.tr("đóng", "close")]]
                    Row {
                        required property var modelData
                        spacing: 6
                        Rectangle {
                            width: keyT.width + 12; height: 19; radius: 5; color: "#40000000"; border.color: "#40ffffff"
                            Text { id: keyT; anchors.centerIn: parent; text: modelData[0]; color: "white"; font.pixelSize: 11 }
                        }
                        Text { text: modelData[1]; color: "#99ffffff"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    }
                }
            }

            // bấm ra ngoài dải ảnh để đóng; lăn chuột để lướt
            MouseArea {
                anchors.fill: parent
                z: -1
                onClicked: root.quit()
                onWheel: wheel => { if (wheel.angleDelta.y < 0 || wheel.angleDelta.x < 0) view.incrementCurrentIndex(); else view.decrementCurrentIndex() }
            }

            Keys.onLeftPressed: view.decrementCurrentIndex()
            Keys.onRightPressed: view.incrementCurrentIndex()
            Keys.onReturnPressed: root.apply()
            Keys.onEnterPressed: root.apply()
            Keys.onSpacePressed: root.apply()
            Keys.onEscapePressed: root.quit()
            Keys.onPressed: event => {
                if (event.text && event.text.trim().length === 1 && !(event.modifiers & Qt.ControlModifier)) {
                    search.forceActiveFocus()
                    search.text += event.text
                    event.accepted = true
                }
            }
        }
    }
}
