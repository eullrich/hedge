import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Popup {
    id: root
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    // Properties
    property string selectedSymbol: ""

    // Signals
    signal marketSelected(string symbol)

    Material.background: Material.color(Material.Grey, Material.Shade900)
    Material.elevation: 6

    // Content
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header section
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            color: Qt.rgba(0, 0, 0, 0.3)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                // Search field
                TextField {
                    id: searchField
                    Layout.fillWidth: true
                    placeholderText: "Search markets..."
                    font.pixelSize: 14

                    onTextChanged: {
                        // Debounce search
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
                            model: ["All Coins", "Trending", "AI", "Defi", "Gaming", "Layer 1", "Layer 2", "Meme"]

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

        // Table header
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: Qt.rgba(0, 0, 0, 0.2)
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.05)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 12

                Label {
                    text: "SYMBOL"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 150
                }

                Label {
                    text: "LAST PRICE"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 120
                }

                Label {
                    text: "24HR CHANGE"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 120
                }

                Label {
                    text: "8HR FUNDING"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 100
                }

                Label {
                    text: "VOLUME"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.preferredWidth: 120
                }

                Label {
                    text: "OPEN INTEREST"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    font.capitalization: Font.AllUppercase
                    opacity: 0.6
                    Layout.fillWidth: true
                }
            }
        }

        // Market list
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ListView {
                id: marketList
                model: marketDataModel
                spacing: 0

                delegate: ItemDelegate {
                    width: marketList.width
                    height: 56

                    // Hover effect
                    background: Rectangle {
                        color: parent.hovered ? Qt.rgba(1, 1, 1, 0.05) : "transparent"
                        border.width: parent.hovered ? 1 : 0
                        border.color: Qt.rgba(1, 1, 1, 0.1)
                    }

                    onClicked: {
                        root.selectedSymbol = model.symbol
                        root.marketSelected(model.symbol)
                        root.close()
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 12

                        // Symbol
                        RowLayout {
                            Layout.preferredWidth: 150
                            spacing: 8

                            Label {
                                text: model.symbol
                                font.pixelSize: 14
                                font.weight: Font.Medium
                            }

                            // Trending indicator
                            Rectangle {
                                visible: model.isTrending
                                width: 6
                                height: 6
                                radius: 3
                                color: Material.color(Material.Orange)
                            }
                        }

                        // Last price
                        Label {
                            Layout.preferredWidth: 120
                            text: "$" + formatPrice(model.lastPrice)
                            font.pixelSize: 14
                        }

                        // 24hr change
                        RowLayout {
                            Layout.preferredWidth: 120
                            spacing: 4

                            Label {
                                text: (model.change24hPct >= 0 ? "+" : "") + model.change24hPct.toFixed(2) + "%"
                                font.pixelSize: 14
                                color: model.change24hPct >= 0 ? "#A5D6A7" : "#EF9A9A"
                            }

                            Label {
                                text: "(" + (model.change24h >= 0 ? "+" : "") + "$" + formatPrice(Math.abs(model.change24h)) + ")"
                                font.pixelSize: 11
                                opacity: 0.6
                            }
                        }

                        // Funding rate
                        Label {
                            Layout.preferredWidth: 100
                            text: formatFundingRate(model.fundingRate)
                            font.pixelSize: 14
                            color: model.fundingRate >= 0 ? "#A5D6A7" : "#EF9A9A"
                        }

                        // Volume
                        Label {
                            Layout.preferredWidth: 120
                            text: "$" + formatVolume(model.volume)
                            font.pixelSize: 14
                        }

                        // Open Interest
                        Label {
                            Layout.fillWidth: true
                            text: "$" + formatVolume(model.openInterest)
                            font.pixelSize: 14
                        }
                    }
                }
            }
        }

        // Footer with status
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: Qt.rgba(0, 0, 0, 0.3)

            Label {
                anchors.centerIn: parent
                text: marketList.count + " markets"
                font.pixelSize: 12
                opacity: 0.6
            }
        }
    }

    // Helper functions
    function formatPrice(price) {
        if (price >= 1000) {
            return price.toLocaleString(Qt.locale(), 'f', 2)
        } else if (price >= 1) {
            return price.toLocaleString(Qt.locale(), 'f', 4)
        } else {
            return price.toLocaleString(Qt.locale(), 'f', 6)
        }
    }

    function formatVolume(volume) {
        if (volume >= 1e9) {
            return (volume / 1e9).toFixed(2) + "B"
        } else if (volume >= 1e6) {
            return (volume / 1e6).toFixed(2) + "M"
        } else if (volume >= 1e3) {
            return (volume / 1e3).toFixed(2) + "K"
        } else {
            return volume.toFixed(2)
        }
    }

    function formatFundingRate(rate) {
        if (rate === 0) {
            return "0.00%"
        }
        // Convert to percentage (funding is usually in decimal form)
        var pct = rate * 100
        return (pct >= 0 ? "+" : "") + pct.toFixed(4) + "%"
    }

    // Open handler - refresh data when opened
    onOpened: {
        searchField.clear()
        if (marketDataModel) {
            marketDataModel.setSearchQuery("")
            marketDataModel.loadMarketData()
        }
    }
}
