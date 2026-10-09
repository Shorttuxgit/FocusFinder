import QtQuick 2.0

Rectangle {
    id: box
    width: 800
    height: 800

    Text {
        id: thetext
        text: "Hello World!"
        y: 200
        anchors.horizontalCenter: box.horizontalCenter
        font.pixelSize: 100
        color: "Red"
        font.bold: true
    }

}