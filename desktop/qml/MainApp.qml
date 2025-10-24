import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

ApplicationWindow {
    id: mainWindow
    width: 1600
    height: 1000
    visible: true
    title: "Hedge - Crypto Pair Trading Analysis"
    color: Material.background

    // Tab navigation
    header: TabBar {
        id: tabBar
        Material.elevation: 4

        TabButton {
            text: "★ Watchlist"
            width: implicitWidth
        }

        TabButton {
            text: "Discovery"
            width: implicitWidth
        }

        TabButton {
            text: "Analysis"
            width: implicitWidth
        }

        TabButton {
            text: "Backtest"
            width: implicitWidth
        }
    }

    // Main content area with stacked pages
    StackLayout {
        anchors.fill: parent
        currentIndex: tabBar.currentIndex

        // Page 1: Watchlist
        WatchlistView {
            onPairSelected: function(coin1, coin2) {
                // Switch to analysis tab and load pair
                tabBar.currentIndex = 2
                analysisView.loadPair(coin1, coin2)
            }

            onBacktestRequested: function(coin1, coin2) {
                // Switch to backtest tab and load pair
                tabBar.currentIndex = 3
                backtestView.loadPair(coin1, coin2)
            }

            onRefreshRequested: {
                // Forward to main window handler
                mainWindow.refreshData()
            }
        }

        // Page 2: Discovery
        DiscoveryView {
            onPairSelected: function(coin1, coin2) {
                // Switch to analysis tab and load pair
                tabBar.currentIndex = 2
                analysisView.loadPair(coin1, coin2)
            }

            onBacktestRequested: function(coin1, coin2) {
                // Switch to backtest tab and load pair
                tabBar.currentIndex = 3
                backtestView.loadPair(coin1, coin2)
            }
        }

        // Page 3: Analysis
        AnalysisView {
            id: analysisView

            onBacktestRequested: function(coin1, coin2) {
                // Switch to backtest tab and load pair
                tabBar.currentIndex = 3
                backtestView.loadPair(coin1, coin2)
            }
        }

        // Page 4: Backtest
        BacktestView {
            id: backtestView
        }
    }

    // Status bar at bottom
    footer: ToolBar {
        Material.elevation: 4

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16

            Label {
                text: "Connected: Hyperliquid"
                font.pixelSize: 12
                opacity: 0.7
            }

            Item { Layout.fillWidth: true }

            Label {
                id: lastUpdateLabel
                text: "Last Update: Never"
                font.pixelSize: 12
                opacity: 0.7
            }

            Label {
                text: "|"
                opacity: 0.3
                Layout.leftMargin: 8
                Layout.rightMargin: 8
            }

            Label {
                id: statusLabel
                text: "Ready"
                font.pixelSize: 12
                opacity: 0.7
            }

            Label {
                text: "|"
                opacity: 0.3
                Layout.leftMargin: 8
                Layout.rightMargin: 8
            }

            Button {
                text: "Force Refresh"
                flat: true
                font.pixelSize: 11
                onClicked: mainWindow.forceRefreshData()
                ToolTip.visible: hovered
                ToolTip.text: "Force full data refresh (ignores freshness check)"
            }
        }
    }

    // Signals to Python
    signal refreshData()
    signal forceRefreshData()  // Force full data refresh (ignores freshness check)
    signal pairSelected(string coin1, string coin2)

    // Functions callable from Python
    function setStatus(message) {
        statusLabel.text = message
    }

    function setLastUpdate(time) {
        lastUpdateLabel.text = "Last Update: " + time
    }
}
