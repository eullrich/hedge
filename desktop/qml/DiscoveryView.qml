import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "components"

Rectangle {
    id: root
    color: Material.background

    // Signals
    signal pairSelected(string coin1, string coin2)
    signal backtestRequested(string coin1, string coin2)

    // State for selected baskets
    property var longCoins: []
    property var shortCoins: []
    property int selectedRow: -1

    function triggerScan() {
        console.log("triggerScan called - longCoins:", longCoins, "shortCoins:", shortCoins)
        if (longCoins.length > 0 && shortCoins.length > 0) {
            scanningIndicator.visible = true
            statusLabel.text = "Analyzing " + longCoins.join('+') + " / " + shortCoins.join('+') + "..."
            statusLabel.opacity = 0.7
            console.log("Calling discoveryModel.scanBaskets...")
            discoveryModel.scanBaskets(longCoins, shortCoins, timeframeCombo.currentIndex)
        } else {
            console.log("Not enough coins selected. Need both long and short.")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Header
        Label {
            text: "Discovery"
            font.pixelSize: 24
            font.weight: Font.Medium
        }

        // Controls row
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Label {
                text: "Long:"
                font.pixelSize: 14
            }

            Button {
                id: longButton
                text: longCoins.length > 0 ? longCoins.join('+') : "Select..."
                Layout.preferredWidth: 180
                onClicked: {
                    longSelector.open()
                }
            }

            Button {
                text: "+"
                Layout.preferredWidth: 40
                enabled: longCoins.length > 0
                onClicked: {
                    longSelector.open()
                }
            }

            Button {
                text: "Clear"
                Layout.preferredWidth: 60
                enabled: longCoins.length > 0
                onClicked: {
                    longCoins = []
                }
            }

            Label {
                text: "÷"
                font.pixelSize: 18
                font.weight: Font.Medium
            }

            Label {
                text: "Short:"
                font.pixelSize: 14
            }

            Button {
                id: shortButton
                text: shortCoins.length > 0 ? shortCoins.join('+') : "Select..."
                Layout.preferredWidth: 180
                onClicked: {
                    shortSelector.open()
                }
            }

            Button {
                text: "+"
                Layout.preferredWidth: 40
                enabled: shortCoins.length > 0
                onClicked: {
                    shortSelector.open()
                }
            }

            Button {
                text: "Clear"
                Layout.preferredWidth: 60
                enabled: shortCoins.length > 0
                onClicked: {
                    shortCoins = []
                }
            }

            Label {
                text: "Timeframe:"
                font.pixelSize: 14
            }

            ComboBox {
                id: timeframeCombo
                model: [
                    "Scalping (1 day)",
                    "Intraday (7 days)",
                    "Swing (60 days)"
                ]
                currentIndex: 1
                Layout.preferredWidth: 160
                onCurrentIndexChanged: {
                    triggerScan()
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "Analyze"
                enabled: selectedRow >= 0
                onClicked: {
                    if (selectedRow >= 0) {
                        var pairData = discoveryModel.data(discoveryModel.index(selectedRow, 0), Qt.DisplayRole)
                        var parts = pairData.split("/")
                        if (parts.length === 2) {
                            root.pairSelected(parts[0].trim(), parts[1].trim())
                        } else {
                            // Single token selected, use with current baskets
                            root.pairSelected(longCoins.join('+'), shortCoins.join('+'))
                        }
                    }
                }
            }

            Button {
                text: "Add to Watchlist"
                enabled: longCoins.length > 0 && shortCoins.length > 0
                onClicked: {
                    console.log("Add to Watchlist clicked")
                    console.log("Long coins:", longCoins, "Short coins:", shortCoins)
                    discoveryModel.addBasketPairToWatchlist(longCoins, shortCoins)
                }
            }

            TextField {
                id: searchField
                placeholderText: "Search coin..."
                Layout.preferredWidth: 120
                onTextChanged: discoveryModel.filterByCoin(searchField.text)
            }

            BusyIndicator {
                id: scanningIndicator
                visible: false
                running: visible
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
            }
        }

        // Table header
        HorizontalHeaderView {
            id: headerView
            Layout.fillWidth: true
            height: 40
            syncView: discoveryTable
            clip: true

            delegate: Rectangle {
                implicitHeight: 40
                color: Qt.rgba(1, 1, 1, 0.05)
                border.width: index === 0 ? 1 : 0
                border.color: Qt.rgba(1, 1, 1, 0.12)

                property var headerLabels: ["Pair", "Correlation", "Coint", "Z-Score", "Signal", "Price", "24h Change", "7d Change"]
                property var sortColumns: ["pair", "correlation", "is_cointegrated", "zscore", "signal", "price", "change_24h", "change_7d"]

                Label {
                    anchors.fill: parent
                    text: parent.headerLabels[index]
                    font.pixelSize: 12
                    font.capitalization: Font.AllUppercase
                    opacity: 0.7
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: parent.sortColumns[index] ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: parent.sortColumns[index] !== ""
                    onClicked: {
                        if (parent.sortColumns[index]) {
                            discoveryModel.sortBy(parent.sortColumns[index])
                        }
                    }
                }
            }
        }

        // Discovery results table
        TableView {
            id: discoveryTable
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: discoveryModel
            rowSpacing: 8
            columnSpacing: 0

            columnWidthProvider: function(column) {
                // Divide width equally among 8 columns, accounting for margins
                return (discoveryTable.width - 24) / 8
            }

            delegate: Rectangle {
                implicitHeight: 60
                color: {
                    if (selectedRow === row) return Qt.rgba(0.3, 0.5, 0.8, 0.3)
                    return hoverHandler.hovered ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.03)
                }
                radius: 4
                border.width: selectedRow === row ? 2 : 1
                border.color: selectedRow === row ? Material.accent : (hoverHandler.hovered ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(1, 1, 1, 0.05))

                required property int row
                required property int column
                required property var display

                HoverHandler {
                    id: hoverHandler
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        selectedRow = row
                    }
                }

                // Column content
                Loader {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    sourceComponent: {
                        switch(parent.column) {
                            case 0: return pairColumn
                            case 1: return correlationColumn
                            case 2: return cointegrationColumn
                            case 3: return zscoreColumn
                            case 4: return signalColumn
                            case 5: return priceColumn
                            case 6: return change24hColumn
                            case 7: return change7dColumn
                            default: return null
                        }
                    }

                    property var cellData: parent.display
                    property int cellRow: parent.row
                }

                // Bottom border
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Qt.rgba(1, 1, 1, 0.1)
                }
            }
        }

        // Status label
        Label {
            id: statusLabel
            text: "Select Long and Short baskets to analyze"
            font.pixelSize: 14
            opacity: 0.5
            Layout.fillWidth: true
        }

        // Connect to scan complete signal
        Connections {
            target: discoveryModel
            function onScanComplete(count) {
                // Hide loading indicator
                scanningIndicator.visible = false

                if (count === 0) {
                    statusLabel.text = "No data available. Select Long and Short baskets to analyze."
                    statusLabel.opacity = 0.7
                } else {
                    statusLabel.text = `Showing ${count} basket pair${count > 1 ? 's' : ''}`
                    statusLabel.opacity = 0.5
                }
            }
        }
    }

    // Column components
    Component {
        id: pairColumn
        Label {
            text: cellData
            font.pixelSize: 16
            font.weight: Font.Medium
            color: Material.foreground
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: correlationColumn
        Label {
            text: typeof cellData === 'number' ? cellData.toFixed(2) : cellData
            font.pixelSize: 14
            color: Material.foreground
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: cointegrationColumn
        Label {
            text: cellData ? "YES" : "NO"
            font.pixelSize: 12
            font.weight: Font.Bold
            color: cellData ? "#A5D6A7" : "#EF9A9A"
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: zscoreColumn
        Label {
            text: typeof cellData === 'number' ? cellData.toFixed(2) : cellData
            font.pixelSize: 14
            font.weight: Font.Bold
            color: Material.foreground
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: signalColumn
        Label {
            text: cellData || "NEUTRAL"
            font.pixelSize: 11
            font.capitalization: Font.AllUppercase
            font.weight: Font.Bold
            color: {
                var sig = cellData || "NEUTRAL"
                if (sig === "LONG") return "#A5D6A7"  // Material.Green
                else if (sig === "SHORT") return "#EF9A9A"  // Material.Red
                else return "#EEEEEE"  // Material.Grey
            }
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: priceColumn
        Label {
            text: typeof cellData === 'number' ? ("$" + cellData.toFixed(4)) : cellData
            font.pixelSize: 14
            color: Material.foreground
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: change24hColumn
        Label {
            text: typeof cellData === 'number' ? (cellData > 0 ? "+" : "") + cellData.toFixed(2) + "%" : "0.00%"
            font.pixelSize: 14
            font.weight: Font.Bold
            color: {
                var val = typeof cellData === 'number' ? cellData : 0
                if (val > 0) return "#A5D6A7"  // Green for positive
                else if (val < 0) return "#EF9A9A"  // Red for negative
                else return "#FFFFFF"  // White for zero
            }
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: change7dColumn
        Label {
            text: typeof cellData === 'number' ? (cellData > 0 ? "+" : "") + cellData.toFixed(2) + "%" : "0.00%"
            font.pixelSize: 14
            font.weight: Font.Bold
            color: {
                var val = typeof cellData === 'number' ? cellData : 0
                if (val > 0) return "#A5D6A7"  // Green for positive
                else if (val < 0) return "#EF9A9A"  // Red for negative
                else return "#FFFFFF"  // White for zero
            }
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }


    // Long basket selector
    BasketSelector {
        id: longSelector
        anchors.centerIn: parent
        width: parent.width * 0.7
        height: parent.height * 0.8

        onCoinSelected: function(coinId) {
            if (longCoins.indexOf(coinId) < 0) {
                longCoins.push(coinId)
                longCoins = longCoins.slice()  // Force property update
            }
            triggerScan()
        }
    }

    // Short basket selector
    BasketSelector {
        id: shortSelector
        anchors.centerIn: parent
        width: parent.width * 0.7
        height: parent.height * 0.8

        onCoinSelected: function(coinId) {
            if (shortCoins.indexOf(coinId) < 0) {
                shortCoins.push(coinId)
                shortCoins = shortCoins.slice()  // Force property update
            }
            triggerScan()
        }
    }

    // Market selector (kept for backwards compatibility, hidden)
    MarketSelector {
        id: marketSelector
        anchors.centerIn: parent
        width: parent.width * 0.85
        height: parent.height * 0.85
        visible: false
    }
}
