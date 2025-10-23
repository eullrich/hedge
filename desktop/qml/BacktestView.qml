import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Rectangle {
    id: root
    color: Material.background

    Connections {
        target: backtestModel
        function onBacktestComplete() {
            resultsGroup.visible = true
        }
        function onErrorOccurred(message) {
            errorLabel.text = message
            errorLabel.visible = true
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Header
        Label {
            text: "Backtest"
            font.pixelSize: 24
            font.weight: Font.Medium
        }

        // Error message
        Label {
            id: errorLabel
            visible: false
            color: Material.Red
            font.pixelSize: 14
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        // Configuration section
        GroupBox {
            title: "Backtest Configuration"
            Layout.fillWidth: true
            Material.elevation: 2

            ColumnLayout {
                anchors.fill: parent
                spacing: 16

                // Pair selection
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    Label {
                        text: "Trading Pair:"
                        font.pixelSize: 14
                    }

                    TextField {
                        id: coin1Field
                        placeholderText: "BTC"
                        Layout.preferredWidth: 100
                    }

                    Label {
                        text: "/"
                        font.pixelSize: 14
                    }

                    TextField {
                        id: coin2Field
                        placeholderText: "ETH"
                        Layout.preferredWidth: 100
                    }

                    Item { Layout.fillWidth: true }
                }

                // Date range
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    Label {
                        text: "Date Range:"
                        font.pixelSize: 14
                    }

                    TextField {
                        id: startDateField
                        placeholderText: "2024-01-01"
                        Layout.preferredWidth: 150
                    }

                    Label {
                        text: "to"
                        font.pixelSize: 14
                    }

                    TextField {
                        id: endDateField
                        placeholderText: "2024-12-31"
                        Layout.preferredWidth: 150
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: backtestModel.isRunning ? "Cancel" : "Run Backtest"
                        highlighted: !backtestModel.isRunning
                        onClicked: {
                            if (backtestModel.isRunning) {
                                backtestModel.cancel()
                            } else {
                                errorLabel.visible = false
                                resultsGroup.visible = false
                                backtestModel.runBacktest(
                                    coin1Field.text || "BTC",
                                    coin2Field.text || "ETH",
                                    startDateField.text || "2024-01-01",
                                    endDateField.text || "2024-12-31"
                                )
                            }
                        }
                    }
                }
            }
        }

        // Progress indicator
        ProgressBar {
            Layout.fillWidth: true
            visible: backtestModel.isRunning
            indeterminate: true
        }

        // Results section
        GroupBox {
            id: resultsGroup
            title: "Backtest Results"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Material.elevation: 2
            visible: false

            ScrollView {
                anchors.fill: parent
                clip: true

                ColumnLayout {
                    width: parent.width
                    spacing: 16

                    // Results cards
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 3
                        rowSpacing: 16
                        columnSpacing: 16

                        // Total Return
                        Rectangle {
                            Layout.fillWidth: true
                            height: 100
                            color: Qt.rgba(1, 1, 1, 0.05)
                            radius: 8
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.12)

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: "TOTAL RETURN"
                                    font.pixelSize: 11
                                    font.capitalization: Font.AllUppercase
                                    opacity: 0.7
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: backtestModel.results.total_return ? backtestModel.results.total_return.toFixed(2) + "%" : "0.00%"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    color: (backtestModel.results.total_return || 0) > 0 ? Material.Green : Material.Red
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        // Sharpe Ratio
                        Rectangle {
                            Layout.fillWidth: true
                            height: 100
                            color: Qt.rgba(1, 1, 1, 0.05)
                            radius: 8
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.12)

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: "SHARPE RATIO"
                                    font.pixelSize: 11
                                    font.capitalization: Font.AllUppercase
                                    opacity: 0.7
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: backtestModel.results.sharpe_ratio ? backtestModel.results.sharpe_ratio.toFixed(2) : "0.00"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        // Max Drawdown
                        Rectangle {
                            Layout.fillWidth: true
                            height: 100
                            color: Qt.rgba(1, 1, 1, 0.05)
                            radius: 8
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.12)

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: "MAX DRAWDOWN"
                                    font.pixelSize: 11
                                    font.capitalization: Font.AllUppercase
                                    opacity: 0.7
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: backtestModel.results.max_drawdown ? backtestModel.results.max_drawdown.toFixed(2) + "%" : "0.00%"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    color: Material.Red
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        // Win Rate
                        Rectangle {
                            Layout.fillWidth: true
                            height: 100
                            color: Qt.rgba(1, 1, 1, 0.05)
                            radius: 8
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.12)

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: "WIN RATE"
                                    font.pixelSize: 11
                                    font.capitalization: Font.AllUppercase
                                    opacity: 0.7
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: backtestModel.results.win_rate ? backtestModel.results.win_rate.toFixed(1) + "%" : "0.0%"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        // Total Trades
                        Rectangle {
                            Layout.fillWidth: true
                            height: 100
                            color: Qt.rgba(1, 1, 1, 0.05)
                            radius: 8
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.12)

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: "TOTAL TRADES"
                                    font.pixelSize: 11
                                    font.capitalization: Font.AllUppercase
                                    opacity: 0.7
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: backtestModel.results.total_trades ? backtestModel.results.total_trades.toString() : "0"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        // Profitable Trades
                        Rectangle {
                            Layout.fillWidth: true
                            height: 100
                            color: Qt.rgba(1, 1, 1, 0.05)
                            radius: 8
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.12)

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: "PROFITABLE TRADES"
                                    font.pixelSize: 11
                                    font.capitalization: Font.AllUppercase
                                    opacity: 0.7
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: backtestModel.results.profitable_trades ? backtestModel.results.profitable_trades.toString() : "0"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    color: Material.Green
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }

                    // Equity curve placeholder
                    Rectangle {
                        Layout.fillWidth: true
                        height: 300
                        color: Qt.rgba(1, 1, 1, 0.05)
                        radius: 8
                        border.width: 1
                        border.color: Qt.rgba(1, 1, 1, 0.12)
                        Layout.topMargin: 16

                        Label {
                            anchors.centerIn: parent
                            text: "Equity curve chart coming soon..."
                            font.pixelSize: 14
                            opacity: 0.5
                        }
                    }
                }
            }
        }

        // Empty state
        Label {
            text: "Configure backtest parameters and click 'Run Backtest' to begin"
            font.pixelSize: 16
            opacity: 0.5
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !backtestModel.isRunning && !resultsGroup.visible
        }
    }
}
