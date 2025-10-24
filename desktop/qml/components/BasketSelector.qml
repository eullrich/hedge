import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Popup {
    id: root
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    // Signals
    signal coinSelected(string coinId)

    Material.background: Material.color(Material.Grey, Material.Shade900)
    Material.elevation: 6

    onOpened: {
        searchField.text = ""

        // Load market data from database (no API calls)
        if (marketDataModel && marketDataModel.rowCount() === 0) {
            marketDataModel.loadFromDatabase()
        }
    }

    // Content
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header section
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 180
            color: Qt.rgba(0, 0, 0, 0.3)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                // Title
                Label {
                    text: "Select Coins"
                    font.pixelSize: 18
                    font.weight: Font.Medium
                }

                // Search field
                TextField {
                    id: searchField
                    Layout.fillWidth: true
                    placeholderText: "Search coins..."
                    font.pixelSize: 14

                    onTextChanged: {
                        searchTimer.restart()
                    }

                    Timer {
                        id: searchTimer
                        interval: 300
                        onTriggered: {
                            if (marketDataModel) {
                                marketDataModel.setSearchQuery(searchField.text)
                            }
                        }
                    }
                }

                // Category tabs
                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    clip: true
                    ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                    RowLayout {
                        spacing: 8

                        Repeater {
                            model: ["All Coins", "AI", "Defi", "Gaming", "Layer 1", "Layer 2", "Meme"]

                            Button {
                                text: modelData
                                flat: true
                                highlighted: marketDataModel ? marketDataModel.selectedCategory === modelData : false
                                font.pixelSize: 12
                                font.capitalization: Font.MixedCase

                                onClicked: {
                                    if (marketDataModel) {
                                        marketDataModel.setCategory(modelData)
                                    }
                                }

                                contentItem: Label {
                                    text: parent.text
                                    font: parent.font
                                    color: parent.highlighted ? "#000000" : Material.foreground
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }

                                background: Rectangle {
                                    color: parent.highlighted ? Material.accent : "transparent"
                                    radius: 4
                                    border.width: parent.highlighted ? 0 : 1
                                    border.color: Qt.rgba(1, 1, 1, 0.12)
                                }
                            }
                        }
                    }
                }

            }
        }


        // Column headers
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: Qt.rgba(1, 1, 1, 0.03)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 16

                Label {
                    text: "Symbol"
                    font.pixelSize: 11
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 120
                }

                Label {
                    text: "Last Price"
                    font.pixelSize: 11
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 100
                    horizontalAlignment: Text.AlignRight
                }

                Label {
                    text: "24hr Change"
                    font.pixelSize: 11
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 90
                    horizontalAlignment: Text.AlignRight
                }

                Label {
                    text: "8hr Funding"
                    font.pixelSize: 11
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 80
                    horizontalAlignment: Text.AlignRight
                }

                Label {
                    text: "Volume"
                    font.pixelSize: 11
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 100
                    horizontalAlignment: Text.AlignRight
                }

                Label {
                    text: "Open Interest"
                    font.pixelSize: 11
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                }
            }
        }

        // Coin list
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ListView {
                id: coinListView
                model: marketDataModel
                spacing: 0

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 48
                    color: hoverHandler.hovered ? Qt.rgba(1, 1, 1, 0.05) : "transparent"

                    required property string symbol
                    required property real lastPrice
                    required property real change24hPct
                    required property real fundingRate
                    required property real volume
                    required property real openInterest

                    HoverHandler {
                        id: hoverHandler
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 16

                        // Symbol
                        Label {
                            text: symbol
                            font.pixelSize: 13
                            font.weight: Font.Medium
                            Layout.preferredWidth: 120
                        }

                        // Last Price
                        Label {
                            text: lastPrice >= 1 ? lastPrice.toLocaleString(Qt.locale(), 'f', 2) : lastPrice.toFixed(6)
                            font.pixelSize: 12
                            Layout.preferredWidth: 100
                            horizontalAlignment: Text.AlignRight
                        }

                        // 24hr Change
                        Label {
                            text: (change24hPct >= 0 ? "+" : "") + change24hPct.toFixed(2) + "%"
                            font.pixelSize: 12
                            color: change24hPct >= 0 ? "#4caf50" : "#f44336"
                            Layout.preferredWidth: 90
                            horizontalAlignment: Text.AlignRight
                        }

                        // 8hr Funding
                        Label {
                            text: (fundingRate * 100).toFixed(3) + "%"
                            font.pixelSize: 12
                            opacity: 0.8
                            Layout.preferredWidth: 80
                            horizontalAlignment: Text.AlignRight
                        }

                        // Volume
                        Label {
                            text: "$" + (volume / 1000000).toFixed(1) + "M"
                            font.pixelSize: 12
                            opacity: 0.8
                            Layout.preferredWidth: 100
                            horizontalAlignment: Text.AlignRight
                        }

                        // Open Interest
                        Label {
                            text: "$" + (openInterest / 1000000).toFixed(1) + "M"
                            font.pixelSize: 12
                            opacity: 0.8
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Qt.rgba(1, 1, 1, 0.08)
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor

                        onClicked: {
                            root.coinSelected(symbol)
                            root.close()
                        }
                    }
                }
            }
        }
    }
}
