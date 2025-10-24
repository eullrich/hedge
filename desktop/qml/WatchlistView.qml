import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "components"

Rectangle {
    id: root
    color: Material.background  // Material Dark background (#121212)

    // Signals
    signal pairSelected(string coin1, string coin2)
    signal backtestRequested(string coin1, string coin2)
    signal refreshRequested()

    // Column widths - all equal
    readonly property int equalColumnWidth: 140
    readonly property var columnNames: ["pair", "ratio", "zscore", "correlation", "", "", "", ""]
    readonly property var headerLabels: ["Pair", "Ratio", "Z-Score", "Corr", "24h Ratio Δ", "7d Ratio Δ", "Signal", "Actions"]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Header with title and refresh button
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Label {
                text: "★ Watchlist"
                font.pixelSize: 24  // Material headline
                font.weight: Font.Medium
                Layout.fillWidth: true
            }

            Button {
                text: "Refresh"
                highlighted: true
                onClicked: root.refreshRequested()
            }
        }

        // Table header
        HorizontalHeaderView {
            id: headerView
            Layout.fillWidth: true
            height: 40
            syncView: tableView
            clip: true

            delegate: Rectangle {
                implicitHeight: 40
                color: Qt.rgba(1, 1, 1, 0.05)
                border.width: index === 0 ? 1 : 0
                border.color: Qt.rgba(1, 1, 1, 0.12)

                Label {
                    anchors.fill: parent
                    text: root.headerLabels[index]
                    font.pixelSize: 12
                    font.capitalization: Font.AllUppercase
                    opacity: 0.7
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: root.columnNames[index] ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: root.columnNames[index] !== ""
                    onClicked: {
                        if (root.columnNames[index]) {
                            watchlistModel.sortBy(root.columnNames[index])
                        }
                    }
                }
            }
        }

        // Table view
        TableView {
            id: tableView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: watchlistModel
            rowSpacing: 8
            columnSpacing: 0

            columnWidthProvider: function(column) {
                // Divide width equally among 8 columns, accounting for margins
                return (tableView.width - 24) / 8
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
                            case 1: return ratioColumn
                            case 2: return zscoreColumn
                            case 3: return correlationColumn
                            case 4: return change24hColumn
                            case 5: return change7dColumn
                            case 6: return signalColumn
                            case 7: return actionsColumn
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

        // Empty state
        Label {
            visible: tableView.rows === 0
            text: "No pairs in watchlist\nUse Discovery to find and add trading pairs"
            font.pixelSize: 14  // Material body
            opacity: 0.5
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.fillHeight: true
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
        id: ratioColumn
        Label {
            text: typeof cellData === 'number' ? cellData.toFixed(4) : cellData
            font.pixelSize: 14
            color: Material.foreground
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
        id: signalColumn
        Label {
            text: cellData || "NEUTRAL"
            font.pixelSize: 11
            font.capitalization: Font.AllUppercase
            font.weight: Font.Bold
            color: {
                var signal = cellData || "NEUTRAL"
                if (signal === "LONG") return "#A5D6A7"  // Material.Green
                else if (signal === "SHORT") return "#EF9A9A"  // Material.Red
                else return "#EEEEEE"  // Material.Grey
            }
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component {
        id: actionsColumn
        RowLayout {
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
                        var pairData = watchlistModel.data(watchlistModel.index(cellRow, 0), Qt.DisplayRole)
                        var parts = pairData.split("/")
                        if (parts.length === 2) {
                            root.pairSelected(parts[0], parts[1])
                        }
                    }
                }
            }

            Label {
                text: "Backtest"
                color: Material.accent
                font.pixelSize: 14

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        // Get pair data from the model
                        var pairData = watchlistModel.data(watchlistModel.index(cellRow, 0), Qt.DisplayRole)
                        var parts = pairData.split("/")
                        if (parts.length === 2) {
                            root.backtestRequested(parts[0], parts[1])
                        }
                    }
                }
            }

            Label {
                text: "Remove"
                color: Material.accent
                font.pixelSize: 14

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        watchlistModel.remove(cellRow)
                    }
                }
            }
        }
    }
}
