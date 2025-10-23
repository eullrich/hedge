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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Header
        Label {
            text: "Pair Discovery"
            font.pixelSize: 24
            font.weight: Font.Medium
        }

        // Controls row
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Label {
                text: "Reference Leg:"
                font.pixelSize: 14
            }

            Button {
                id: referenceButton
                text: marketSelector.selectedSymbol || "Select Market"
                Layout.preferredWidth: 200
                onClicked: marketSelector.open()
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
                Layout.preferredWidth: 200
                onCurrentIndexChanged: {
                    // Trigger rescan if we have a reference coin selected
                    if (marketSelector.selectedSymbol) {
                        scanningIndicator.visible = true
                        statusLabel.text = "Loading pairs for " + marketSelector.selectedSymbol + "..."
                        statusLabel.opacity = 0.7
                        discoveryModel.scanPairs(marketSelector.selectedSymbol, currentIndex)
                    }
                }
            }

            Item { Layout.fillWidth: true }

            BusyIndicator {
                id: scanningIndicator
                visible: false
                running: visible
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
            }
        }

        // Auto-trigger scan when reference leg changes
        Connections {
            target: marketSelector
            function onMarketSelected(symbol) {
                scanningIndicator.visible = true
                statusLabel.text = "Loading pairs for " + symbol + "..."
                statusLabel.opacity = 0.7
                discoveryModel.scanPairs(symbol, timeframeCombo.currentIndex)
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

                property var headerLabels: ["Pair", "Correlation", "Coint", "Z-Score", "Signal", "Price", "24h Change", "7d Change", "Actions"]
                property var sortColumns: ["pair", "correlation", "is_cointegrated", "zscore", "signal", "price", "change_24h", "change_7d", ""]

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
                // Divide width equally among 9 columns, accounting for margins
                return (discoveryTable.width - 24) / 9
            }

            delegate: Rectangle {
                implicitHeight: 60
                color: hoverHandler.hovered ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.03)
                radius: 4
                border.width: 1
                border.color: hoverHandler.hovered ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(1, 1, 1, 0.05)

                required property int row
                required property int column
                required property var display

                HoverHandler {
                    id: hoverHandler
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
                            case 8: return actionsColumn
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
            text: "Click 'Scan Pairs' to discover trading opportunities"
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
                    statusLabel.text = "No correlated pairs found. Try a different reference coin or timeframe."
                    statusLabel.opacity = 0.7
                } else {
                    statusLabel.text = `Found ${count} correlated pairs`
                    statusLabel.opacity = 0.5
                }
            }
        }
    }

    // Market selector popup
    MarketSelector {
        id: marketSelector
        anchors.centerIn: parent
        width: parent.width * 0.85
        height: parent.height * 0.85

        onMarketSelected: function(symbol) {
            console.log("Market selected:", symbol)
            // Symbol is already stored in selectedSymbol property
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

    Component {
        id: actionsColumn
        Item {
            RowLayout {
                anchors.centerIn: parent
                spacing: 16

                Label {
                    text: "Analyze"
                    color: Material.accent
                    font.pixelSize: 14

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            // Get pair data from the model
                            var pairData = discoveryModel.data(discoveryModel.index(cellRow, 0), Qt.DisplayRole)
                            var parts = pairData.split("/")
                            if (parts.length === 2) {
                                root.pairSelected(parts[0], parts[1])
                            }
                        }
                    }
                }

                Label {
                    text: "Add to Watchlist"
                    color: Material.accent
                    font.pixelSize: 14

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            discoveryModel.addToWatchlist(cellRow)
                        }
                    }
                }
            }
        }
    }
}
