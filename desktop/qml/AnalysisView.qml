import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtGraphs

Rectangle {
    id: root
    color: Material.background

    // Signals
    signal backtestRequested(string coin1, string coin2)

    // Chart size state
    property int chartHeight: 400  // Default: Normal size
    property var chartSizes: ({
        "Compact": 300,
        "Normal": 400,
        "Large": 500,
        "Full": 800
    })

    Connections {
        target: analysisModel
        function onPairLoaded(coin1, coin2) {
            console.log("Pair loaded:", coin1 + "/" + coin2)
            updateCharts()
        }
        function onErrorOccurred(message) {
            errorLabel.text = message
            errorLabel.visible = true
        }
        function onChartDataChanged() {
            updateCharts()
        }
    }

    // Binary search to find nearest timestamp index (O(log n))
    function findNearestIndex(timestamps, targetMs) {
        if (timestamps.length === 0) return -1

        var left = 0
        var right = timestamps.length - 1
        var closestIdx = 0
        var minDiff = Math.abs(timestamps[0] - targetMs)

        while (left <= right) {
            var mid = Math.floor((left + right) / 2)
            var diff = Math.abs(timestamps[mid] - targetMs)

            if (diff < minDiff) {
                minDiff = diff
                closestIdx = mid
            }

            if (timestamps[mid] < targetMs) {
                left = mid + 1
            } else if (timestamps[mid] > targetMs) {
                right = mid - 1
            } else {
                return mid  // Exact match
            }
        }

        return closestIdx
    }

    // Zoom helper for value axis (Y-axis)
    function zoomValueAxis(axis, delta, mouseY, chartHeight) {
        var currentMin = axis.min
        var currentMax = axis.max
        var range = currentMax - currentMin

        // Zoom factor (wheel delta is typically ±120 per notch)
        var zoomFactor = delta > 0 ? 0.9 : 1.1
        var newRange = range * zoomFactor

        // Calculate zoom center based on mouse position
        var relativePos = mouseY / chartHeight
        var centerValue = currentMax - (range * relativePos)

        // Calculate new min/max centered on mouse position
        var offsetFromCenter = newRange * relativePos
        axis.min = centerValue - (newRange - offsetFromCenter)
        axis.max = centerValue + offsetFromCenter
    }

    // Zoom helper for datetime axis (X-axis)
    function zoomDateTimeAxis(axis, delta, mouseX, chartWidth) {
        var currentMin = axis.min.getTime()
        var currentMax = axis.max.getTime()
        var range = currentMax - currentMin

        var zoomFactor = delta > 0 ? 0.9 : 1.1
        var newRange = range * zoomFactor

        // Calculate zoom center based on mouse position
        var relativePos = mouseX / chartWidth
        var centerTime = currentMin + (range * relativePos)

        // Calculate new min/max centered on mouse position
        var offsetFromCenter = newRange * relativePos
        axis.min = new Date(centerTime - offsetFromCenter)
        axis.max = new Date(centerTime + (newRange - offsetFromCenter))
    }

    function updateCharts() {
        console.log("Updating charts...")

        // Clear existing data
        ratioSeries.clear()
        zscoreSeries.clear()
        coin1NormSeries.clear()
        coin2NormSeries.clear()
        betaSeries.clear()
        volatilitySeries.clear()

        // Populate combined normalized prices chart (ratio + both coins)
        var timestamps = analysisModel.ratioTimestamps
        var ratioValues = analysisModel.ratioValues
        var coin1Values = analysisModel.coin1Values
        var coin2Values = analysisModel.coin2Values

        console.log("Ratio values length:", ratioValues.length, "Timestamps length:", timestamps.length)
        console.log("Coin1 values length:", coin1Values.length, "Coin2 values length:", coin2Values.length)
        if (ratioValues.length > 0 && timestamps.length > 0) {
            console.log("First ratio value:", ratioValues[0], "Last:", ratioValues[ratioValues.length - 1])
            console.log("First coin1 value:", coin1Values[0], "Last:", coin1Values[coin1Values.length - 1])
            console.log("First coin2 value:", coin2Values[0], "Last:", coin2Values[coin2Values.length - 1])
            console.log("First timestamp:", timestamps[0], "Last:", timestamps[timestamps.length - 1])

            ratioSeries.clear()
            ratioEmaSeries.clear()
            ratioBbUpperLine.clear()
            ratioBbLowerLine.clear()
            coin1NormSeries.clear()
            coin2NormSeries.clear()

            var emaTimestamps = analysisModel.ratioEmaTimestamps
            var emaValues = analysisModel.ratioEma
            var bbUpper = analysisModel.ratioBbUpper
            var bbLower = analysisModel.ratioBbLower

            console.log("EMA values length:", emaValues.length, "First EMA:", emaValues[0], "First BB upper:", bbUpper[0], "First BB lower:", bbLower[0])

            // Collect all values for range calculation
            var allValues = []

            for (var i = 0; i < ratioValues.length; i++) {
                // Add ratio
                ratioSeries.append(timestamps[i], ratioValues[i])
                allValues.push(ratioValues[i])

                // Add coin 1 normalized (if available)
                if (i < coin1Values.length && coin1Values[i] !== null && !isNaN(coin1Values[i])) {
                    coin1NormSeries.append(timestamps[i], coin1Values[i])
                    allValues.push(coin1Values[i])
                }

                // Add coin 2 normalized (if available)
                if (i < coin2Values.length && coin2Values[i] !== null && !isNaN(coin2Values[i])) {
                    coin2NormSeries.append(timestamps[i], coin2Values[i])
                    allValues.push(coin2Values[i])
                }

                // Add EMA and BB (skip null values)
                if (i < emaValues.length && emaValues[i] !== null && !isNaN(emaValues[i]) &&
                    bbUpper[i] !== null && !isNaN(bbUpper[i]) &&
                    bbLower[i] !== null && !isNaN(bbLower[i])) {
                    ratioEmaSeries.append(timestamps[i], emaValues[i])
                    ratioBbUpperLine.append(timestamps[i], bbUpper[i])
                    ratioBbLowerLine.append(timestamps[i], bbLower[i])
                    allValues.push(bbUpper[i])
                    allValues.push(bbLower[i])
                }
            }
            console.log("Ratio series point count:", ratioSeries.count)
            console.log("Coin1 norm series point count:", coin1NormSeries.count)
            console.log("Coin2 norm series point count:", coin2NormSeries.count)

            // Set axis ranges for combined chart
            ratioAxisX.min = new Date(timestamps[0])
            ratioAxisX.max = new Date(timestamps[timestamps.length - 1])

            // Calculate min/max from all visible data
            var minVal = Math.min(...allValues)
            var maxVal = Math.max(...allValues)
            ratioAxisY.min = minVal * 0.98
            ratioAxisY.max = maxVal * 1.02

            // Store original ranges for zoom reset
            ratioChart.origXMin = ratioAxisX.min
            ratioChart.origXMax = ratioAxisX.max
            ratioChart.origYMin = ratioAxisY.min
            ratioChart.origYMax = ratioAxisY.max
        }

        // Populate z-score chart
        var zscoreTimestamps = analysisModel.zscoreTimestamps
        var zscoreValues = analysisModel.zscoreValues
        console.log("Z-score values length:", zscoreValues.length)
        if (zscoreValues.length > 0 && zscoreTimestamps.length > 0) {
            zscoreThresholdPlus2.clear()
            zscoreThresholdMinus2.clear()
            zscoreZeroLine.clear()

            var startDate = new Date(zscoreTimestamps[0])
            var endDate = new Date(zscoreTimestamps[zscoreTimestamps.length - 1])

            for (var i = 0; i < zscoreValues.length; i++) {
                var date = new Date(zscoreTimestamps[i])
                zscoreSeries.append(date, zscoreValues[i])
            }

            // Add threshold lines
            zscoreThresholdPlus2.append(startDate, 2.0)
            zscoreThresholdPlus2.append(endDate, 2.0)

            zscoreThresholdMinus2.append(startDate, -2.0)
            zscoreThresholdMinus2.append(endDate, -2.0)

            zscoreZeroLine.append(startDate, 0.0)
            zscoreZeroLine.append(endDate, 0.0)

            zscoreAxisX.min = startDate
            zscoreAxisX.max = endDate

            // Store original ranges for zoom reset
            zscoreChart.origXMin = zscoreAxisX.min
            zscoreChart.origXMax = zscoreAxisX.max
            zscoreChart.origYMin = zscoreAxisY.min
            zscoreChart.origYMax = zscoreAxisY.max
        }


        // Populate spread chart
        var spreadTimestamps = analysisModel.spreadTimestamps
        var spreadOpens = analysisModel.spreadOpen
        var spreadHighs = analysisModel.spreadHigh
        var spreadLows = analysisModel.spreadLow
        var spreadCloses = analysisModel.spreadClose

        console.log("Spread values length:", spreadCloses.length)
        if (spreadCloses.length > 0 && spreadTimestamps.length > 0) {
            spreadHighLine.clear()
            spreadLowLine.clear()
            spreadCloseLine.clear()

            console.log("First 3 spread values:")
            for (var i = 0; i < Math.min(3, spreadCloses.length); i++) {
                console.log("  [" + i + "] O:" + spreadOpens[i] + " H:" + spreadHighs[i] + " L:" + spreadLows[i] + " C:" + spreadCloses[i])
            }

            for (var i = 0; i < spreadCloses.length; i++) {
                var date = new Date(spreadTimestamps[i])

                // High and low lines for AreaSeries
                spreadHighLine.append(date, spreadHighs[i])
                spreadLowLine.append(date, spreadLows[i])

                // Close line
                spreadCloseLine.append(date, spreadCloses[i])
            }

            console.log("Spread series populated. High line count:", spreadHighLine.count, "Low line count:", spreadLowLine.count, "Close line count:", spreadCloseLine.count)

            // Set axis ranges for spread chart
            spreadAxisX.min = new Date(spreadTimestamps[0])
            spreadAxisX.max = new Date(spreadTimestamps[spreadTimestamps.length - 1])
            var minSpread = Math.min(...spreadLows)
            var maxSpread = Math.max(...spreadHighs)

            // Add padding to Y-axis range (works for both positive and negative values)
            var spreadRange = maxSpread - minSpread
            var padding = spreadRange * 0.1  // 10% padding
            spreadAxisY.min = minSpread - padding
            spreadAxisY.max = maxSpread + padding

            console.log("Spread Y-axis range:", spreadAxisY.min, "to", spreadAxisY.max, "(min spread:", minSpread, "max spread:", maxSpread, ")")

            // Store original ranges for zoom reset
            spreadChart.origXMin = spreadAxisX.min
            spreadChart.origXMax = spreadAxisX.max
            spreadChart.origYMin = spreadAxisY.min
            spreadChart.origYMax = spreadAxisY.max
        }

        // Populate rolling correlation chart
        var corrTimestamps = analysisModel.rollingCorrTimestamps
        var corrValues = analysisModel.rollingCorrValues
        console.log("Rolling correlation values length:", corrValues.length)
        if (corrValues.length > 0 && corrTimestamps.length > 0) {
            rollingCorrSeries.clear()

            for (var i = 0; i < corrValues.length; i++) {
                if (corrValues[i] !== null && !isNaN(corrValues[i])) {
                    rollingCorrSeries.append(corrTimestamps[i], corrValues[i])
                }
            }

            // Set axis ranges for correlation chart
            corrAxisX.min = new Date(corrTimestamps[0])
            corrAxisX.max = new Date(corrTimestamps[corrTimestamps.length - 1])
            corrAxisY.min = -1.05
            corrAxisY.max = 1.05

            // Store original ranges for zoom reset
            corrChart.origXMin = corrAxisX.min
            corrChart.origXMax = corrAxisX.max
            corrChart.origYMin = corrAxisY.min
            corrChart.origYMax = corrAxisY.max
        }

        // Populate beta evolution chart
        var betaTimestamps = analysisModel.betaTimestamps
        var betaValues = analysisModel.betaValues
        var betaCiUpper = analysisModel.betaCiUpper
        var betaCiLower = analysisModel.betaCiLower
        console.log("Beta values length:", betaValues.length)
        console.log("First 3 beta values:", betaValues.slice(0, 3))
        if (betaValues.length > 0 && betaTimestamps.length > 0) {
            betaSeries.clear()
            betaLine.clear()
            betaCiUpperLine.clear()
            betaCiLowerLine.clear()
            betaRefLine.clear()

            var betaPointsAdded = 0
            for (var i = 0; i < betaValues.length; i++) {
                if (betaValues[i] !== null && !isNaN(betaValues[i])) {
                    var date = new Date(betaTimestamps[i])
                    betaSeries.append(date, betaValues[i])
                    betaLine.append(date, betaValues[i])
                    betaPointsAdded++

                    if (betaCiUpper[i] !== null && !isNaN(betaCiUpper[i]) && betaCiLower[i] !== null && !isNaN(betaCiLower[i])) {
                        betaCiUpperLine.append(date, betaCiUpper[i])
                        betaCiLowerLine.append(date, betaCiLower[i])
                    }
                }
            }
            console.log("Beta points added:", betaPointsAdded)

            // Add reference line at beta = 1.0
            var startDate = new Date(betaTimestamps[0])
            var endDate = new Date(betaTimestamps[betaTimestamps.length - 1])
            betaRefLine.append(startDate, 1.0)
            betaRefLine.append(endDate, 1.0)

            // Set axis ranges for beta chart
            betaAxisX.min = startDate
            betaAxisX.max = endDate

            // Calculate Y-axis range from all values (beta + CI)
            var allBetaVals = betaValues.concat(betaCiUpper.filter(v => v !== null), betaCiLower.filter(v => v !== null))
            var minBeta = Math.min(...allBetaVals)
            var maxBeta = Math.max(...allBetaVals)
            var betaRange = maxBeta - minBeta
            var betaPadding = betaRange * 0.1
            betaAxisY.min = minBeta - betaPadding
            betaAxisY.max = maxBeta + betaPadding

            // Store original ranges for zoom reset
            betaChart.origXMin = betaAxisX.min
            betaChart.origXMax = betaAxisX.max
            betaChart.origYMin = betaAxisY.min
            betaChart.origYMax = betaAxisY.max
        }

        // Populate volatility chart
        var volTimestamps = analysisModel.volatilityTimestamps
        var volValues = analysisModel.volatilityValues
        console.log("Volatility values length:", volValues.length)
        console.log("First 3 volatility values:", volValues.slice(0, 3))
        if (volValues.length > 0 && volTimestamps.length > 0) {
            volatilitySeries.clear()

            var volPointsAdded = 0
            for (var i = 0; i < volValues.length; i++) {
                if (volValues[i] !== null && !isNaN(volValues[i])) {
                    volatilitySeries.append(volTimestamps[i], volValues[i])
                    volPointsAdded++
                }
            }
            console.log("Volatility points added:", volPointsAdded)

            // Set axis ranges for volatility chart
            volatilityAxisX.min = new Date(volTimestamps[0])
            volatilityAxisX.max = new Date(volTimestamps[volTimestamps.length - 1])

            // Filter out null values for min/max calculation
            var validVolValues = volValues.filter(v => v !== null && !isNaN(v))
            if (validVolValues.length > 0) {
                var minVol = Math.min(...validVolValues)
                var maxVol = Math.max(...validVolValues)
                var volRange = maxVol - minVol
                var volPadding = volRange * 0.1
                volatilityAxisY.min = Math.max(0, minVol - volPadding)  // Don't go below 0
                volatilityAxisY.max = maxVol + volPadding
            }

            // Store original ranges for zoom reset
            volatilityChart.origXMin = volatilityAxisX.min
            volatilityChart.origXMax = volatilityAxisX.max
            volatilityChart.origYMin = volatilityAxisY.min
            volatilityChart.origYMax = volatilityAxisY.max
        }

        console.log("Charts updated!")
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Label {
                text: "Analysis" + (analysisModel.currentPair ? " - " + analysisModel.currentPair : "")
                font.pixelSize: 24
                font.weight: Font.Medium
                Layout.fillWidth: true
            }

            Button {
                text: "Refresh"
                onClicked: {
                    // Reload with current settings
                    if (analysisModel.currentPair) {
                        var parts = analysisModel.currentPair.split("/")
                        if (parts.length === 2) {
                            loadPairWithSettings(parts[0], parts[1])
                        }
                    }
                }
                enabled: !analysisModel.isLoading && analysisModel.currentPair !== ""
            }

            Button {
                text: "Backtest"
                highlighted: true
                onClicked: {
                    // Send to backtest page with current pair
                    if (analysisModel.currentPair) {
                        var parts = analysisModel.currentPair.split("/")
                        if (parts.length === 2) {
                            root.backtestRequested(parts[0], parts[1])
                        }
                    }
                }
                enabled: !analysisModel.isLoading && analysisModel.currentPair !== ""
            }

            Rectangle {
                width: 1
                height: 30
                color: Qt.rgba(1, 1, 1, 0.12)
            }

            Label {
                text: "Chart Size:"
                font.pixelSize: 14
            }

            ComboBox {
                id: chartSizeCombo
                model: ["Compact", "Normal", "Large", "Full"]
                currentIndex: 1  // Default to "Normal"
                Layout.preferredWidth: 120
                onCurrentTextChanged: {
                    root.chartHeight = root.chartSizes[currentText]
                }
            }
        }

        // Analysis controls
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            visible: analysisModel.currentPair !== ""

            Label {
                text: "Timeframe:"
                font.pixelSize: 14
            }

            ComboBox {
                id: timeframeCombo
                model: ["5min", "1hour", "4hour"]
                currentIndex: 1  // Default to 1hour
                Layout.preferredWidth: 100
                onCurrentTextChanged: {
                    if (analysisModel.currentPair) {
                        var parts = analysisModel.currentPair.split("/")
                        if (parts.length === 2) {
                            loadPairWithSettings(parts[0], parts[1])
                        }
                    }
                }
            }

            Item {
                Layout.fillWidth: true
            }
        }

        // Error message
        Label {
            id: errorLabel
            visible: false
            color: Material.color(Material.Red)
            font.pixelSize: 14
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        // Metrics cards
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            visible: !analysisModel.isLoading && analysisModel.currentPair !== ""

            // Correlation card
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 8
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Label {
                        text: "CORRELATION"
                        font.pixelSize: 12
                        font.capitalization: Font.AllUppercase
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: analysisModel.correlation.toFixed(4)
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        color: analysisModel.correlation > 0.7 ? "#A5D6A7" : "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }

            // Z-Score card
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 8
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Label {
                        text: "Z-SCORE"
                        font.pixelSize: 12
                        font.capitalization: Font.AllUppercase
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: analysisModel.zscore.toFixed(2)
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        color: {
                            if (analysisModel.zscore > 2.0) return "#EF9A9A"
                            if (analysisModel.zscore < -2.0) return "#A5D6A7"
                            return "#FFFFFF"
                        }
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }

            // Half-life card
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 8
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Label {
                        text: "HALF-LIFE"
                        font.pixelSize: 12
                        font.capitalization: Font.AllUppercase
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: analysisModel.halfLife.toFixed(1) + " days"
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        color: {
                            if (analysisModel.halfLife > 0 && analysisModel.halfLife <= 30) return "#A5D6A7"
                            return "#FFFFFF"
                        }
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }

            // Signal card
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 8
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Label {
                        text: "SIGNAL"
                        font.pixelSize: 12
                        font.capitalization: Font.AllUppercase
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: analysisModel.signal
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        color: {
                            if (analysisModel.signal === "LONG") return "#A5D6A7"
                            if (analysisModel.signal === "SHORT") return "#EF9A9A"
                            return "#FFFFFF"
                        }
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }

            // Cointegration card
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 8
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Label {
                        text: "COINTEGRATION"
                        font.pixelSize: 12
                        font.capitalization: Font.AllUppercase
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: analysisModel.isCointegrated ? "YES" : "NO"
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        color: analysisModel.isCointegrated ? "#A5D6A7" : "#EF9A9A"
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: "p = " + analysisModel.cointPvalue.toFixed(4)
                        font.pixelSize: 11
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }

            // 24h Ratio Change card
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 8
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Label {
                        text: "24H RATIO Δ"
                        font.pixelSize: 12
                        font.capitalization: Font.AllUppercase
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: (analysisModel.change24h > 0 ? "+" : "") + analysisModel.change24h.toFixed(2) + "%"
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        color: {
                            if (analysisModel.change24h > 0) return "#A5D6A7"
                            else if (analysisModel.change24h < 0) return "#EF9A9A"
                            return "#FFFFFF"
                        }
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }

            // 7d Ratio Change card
            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 8
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8

                    Label {
                        text: "7D RATIO Δ"
                        font.pixelSize: 12
                        font.capitalization: Font.AllUppercase
                        opacity: 0.7
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }

                    Label {
                        text: (analysisModel.change7d > 0 ? "+" : "") + analysisModel.change7d.toFixed(2) + "%"
                        font.pixelSize: 32
                        font.weight: Font.Bold
                        color: {
                            if (analysisModel.change7d > 0) return "#A5D6A7"
                            else if (analysisModel.change7d < 0) return "#EF9A9A"
                            return "#FFFFFF"
                        }
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }
            }
        }

        // Charts with custom scrolling
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !analysisModel.isLoading && analysisModel.currentPair !== ""

            Flickable {
                id: chartFlickable
                anchors.fill: parent
                anchors.rightMargin: 16  // Space for scrollbar
                contentHeight: chartsColumn.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                // Smooth scrolling
                flickDeceleration: 2000
                maximumFlickVelocity: 2500

                ColumnLayout {
                    id: chartsColumn
                    width: chartFlickable.width
                    spacing: 16

                    // Combined Normalized Prices Chart (Ratio + Both Coins)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.chartHeight
                    color: Qt.rgba(1, 1, 1, 0.05)
                    radius: 8
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.12)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        RowLayout {
                            spacing: 16

                            Label {
                                text: "Normalized Prices (Base=100)"
                                font.pixelSize: 14
                                font.weight: Font.Medium
                                color: Material.foreground
                            }

                            // Toggle checkboxes
                            CheckBox {
                                id: showRatioCheck
                                text: "Ratio"
                                checked: true
                                font.pixelSize: 12
                            }

                            CheckBox {
                                id: showCoin1Check
                                text: analysisModel.currentPair.split("/")[0] || "Coin 1"
                                checked: true
                                font.pixelSize: 12
                            }

                            CheckBox {
                                id: showCoin2Check
                                text: analysisModel.currentPair.split("/")[1] || "Coin 2"
                                checked: true
                                font.pixelSize: 12
                            }

                            Item { Layout.fillWidth: true }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            GraphsView {
                                id: ratioChart
                                anchors.fill: parent

                                // Store original axis ranges for reset
                                property var origXMin
                                property var origXMax
                                property real origYMin
                                property real origYMax

                                theme: GraphsTheme {
                                    colorScheme: GraphsTheme.ColorScheme.Dark

                                    // Grid lines
                                    grid.mainColor: Qt.rgba(1, 1, 1, 0.1)
                                    grid.subColor: Qt.rgba(1, 1, 1, 0.05)

                                    // Axis label TEXT color (white)
                                    labelTextColor: Material.foreground

                                    // Axis LINE colors (subtle white)
                                    axisX.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                    axisY.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                }

                                axisX: DateTimeAxis {
                                    id: ratioAxisX
                                    labelFormat: "MMM dd"
                                }

                                axisY: ValueAxis {
                                    id: ratioAxisY
                                    labelFormat: "%.4f"
                                }

                                // Bollinger Bands (upper)
                                LineSeries {
                                    id: ratioBbUpperLine
                                    name: "BB Upper"
                                    visible: false
                                }

                                // Bollinger Bands (lower)
                                LineSeries {
                                    id: ratioBbLowerLine
                                    name: "BB Lower"
                                    visible: false
                                }

                                // Bollinger Bands area
                                AreaSeries {
                                    id: ratioBbArea
                                    name: "Bollinger Bands"
                                    upperSeries: ratioBbUpperLine
                                    lowerSeries: ratioBbLowerLine
                                    color: Qt.rgba(0.5, 0.5, 0.5, 0.1)
                                    borderColor: Qt.rgba(0.7, 0.7, 0.7, 0.3)
                                    borderWidth: 1
                                }

                                // EMA line
                                LineSeries {
                                    id: ratioEmaSeries
                                    name: "EMA(20)"
                                    color: "#FFA726"  // Orange
                                    width: 1.5
                                }

                                // Ratio line (on top)
                                LineSeries {
                                    id: ratioSeries
                                    name: "Ratio"
                                    color: "#90CAF9"  // Material.Blue in dark theme
                                    width: 2
                                    visible: showRatioCheck.checked
                                }

                                // Coin 1 normalized price
                                LineSeries {
                                    id: coin1NormSeries
                                    name: analysisModel.currentPair.split("/")[0] || "Coin 1"
                                    color: "#80DEEA"  // Material.Cyan in dark theme
                                    width: 2
                                    visible: showCoin1Check.checked
                                }

                                // Coin 2 normalized price
                                LineSeries {
                                    id: coin2NormSeries
                                    name: analysisModel.currentPair.split("/")[1] || "Coin 2"
                                    color: "#FFCC80"  // Material.Orange in dark theme
                                    width: 2
                                    visible: showCoin2Check.checked
                                }
                            }

                            // Hover overlay for tooltip and zoom
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                propagateComposedEvents: true

                                property point panStart
                                property var panXMin
                                property var panXMax
                                property real panYMin
                                property real panYMax

                                onPositionChanged: function(mouse) {
                                    // Handle panning
                                    if (pressedButtons & Qt.RightButton) {
                                        var dx = mouse.x - panStart.x
                                        var dy = mouse.y - panStart.y

                                        var xRange = panXMax.getTime() - panXMin.getTime()
                                        var yRange = panYMax - panYMin

                                        var xShift = -(dx / width) * xRange
                                        var yShift = (dy / height) * yRange

                                        ratioAxisX.min = new Date(panXMin.getTime() + xShift)
                                        ratioAxisX.max = new Date(panXMax.getTime() + xShift)
                                        ratioAxisY.min = panYMin + yShift
                                        ratioAxisY.max = panYMax + yShift
                                        return
                                    }

                                    // Handle tooltip
                                    var timestamps = analysisModel.ratioTimestamps
                                    var values = analysisModel.ratioValues

                                    if (timestamps.length === 0 || values.length === 0) {
                                        ratioTooltip.visible = false
                                        return
                                    }

                                    var chartWidth = ratioChart.width
                                    var timeRange = ratioAxisX.max.getTime() - ratioAxisX.min.getTime()
                                    var mouseTimeMs = ratioAxisX.min.getTime() + (mouse.x / chartWidth) * timeRange

                                    var idx = findNearestIndex(timestamps, mouseTimeMs)

                                    if (idx >= 0) {
                                        var date = new Date(timestamps[idx])
                                        ratioTooltip.x = mouse.x + 10
                                        ratioTooltip.y = mouse.y - 40
                                        ratioTooltip.text = Qt.formatDateTime(date, "MMM dd hh:mm") + "\nRatio: " + values[idx].toFixed(2)
                                        ratioTooltip.visible = true
                                    }
                                }

                                onPressed: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        panStart = Qt.point(mouse.x, mouse.y)
                                        panXMin = ratioAxisX.min
                                        panXMax = ratioAxisX.max
                                        panYMin = ratioAxisY.min
                                        panYMax = ratioAxisY.max
                                    }
                                }

                                onWheel: function(wheel) {
                                    if (wheel.modifiers & Qt.ShiftModifier) {
                                        // Shift + Wheel: Zoom X-axis (easier than Ctrl)
                                        zoomDateTimeAxis(ratioAxisX, wheel.angleDelta.y, wheel.x, width)
                                        wheel.accepted = true
                                    } else if (wheel.modifiers & Qt.ControlModifier) {
                                        // Ctrl + Wheel: Zoom Y-axis
                                        zoomValueAxis(ratioAxisY, wheel.angleDelta.y, wheel.y, height)
                                        wheel.accepted = true
                                    } else {
                                        // No modifier: Page scroll (let Flickable handle it)
                                        wheel.accepted = false
                                    }
                                }

                                onDoubleClicked: function(mouse) {
                                    // Reset zoom
                                    if (ratioChart.origXMin) {
                                        ratioAxisX.min = ratioChart.origXMin
                                        ratioAxisX.max = ratioChart.origXMax
                                        ratioAxisY.min = ratioChart.origYMin
                                        ratioAxisY.max = ratioChart.origYMax
                                    }
                                }

                                onExited: {
                                    ratioTooltip.visible = false
                                }
                            }

                            // Tooltip
                            Rectangle {
                                id: ratioTooltip
                                visible: false
                                width: ratioTooltipText.width + 16
                                height: ratioTooltipText.height + 12
                                color: Qt.rgba(0.1, 0.1, 0.1, 0.95)
                                radius: 4
                                border.width: 1
                                border.color: "#90CAF9"
                                z: 1000

                                property alias text: ratioTooltipText.text

                                Label {
                                    id: ratioTooltipText
                                    anchors.centerIn: parent
                                    color: Material.foreground
                                    font.pixelSize: 11
                                }
                            }

                        }
                    }
                    }

                    // Z-Score Chart
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.chartHeight
                    color: Qt.rgba(1, 1, 1, 0.05)
                    radius: 8
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.12)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Label {
                            text: "Z-Score"
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: Material.foreground
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            GraphsView {
                                id: zscoreChart
                                anchors.fill: parent

                                // Store original axis ranges for reset
                                property var origXMin
                                property var origXMax
                                property real origYMin
                                property real origYMax

                                theme: GraphsTheme {
                                    colorScheme: GraphsTheme.ColorScheme.Dark

                                    // Grid lines
                                    grid.mainColor: Qt.rgba(1, 1, 1, 0.1)
                                    grid.subColor: Qt.rgba(1, 1, 1, 0.05)

                                    // Axis label TEXT color (white)
                                    labelTextColor: Material.foreground

                                    // Axis LINE colors (subtle white)
                                    axisX.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                    axisY.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                }

                                axisX: DateTimeAxis {
                                    id: zscoreAxisX
                                    labelFormat: "MMM dd"
                                }

                                axisY: ValueAxis {
                                    id: zscoreAxisY
                                    min: -3
                                    max: 3
                                    labelFormat: "%.1f"
                                }

                                LineSeries {
                                    id: zscoreSeries
                                    name: "Z-Score"
                                    color: "#CE93D8"  // Material.Purple in dark theme
                                    width: 2
                                }

                                // +2 threshold line
                                LineSeries {
                                    id: zscoreThresholdPlus2
                                    name: "+2σ"
                                    color: Material.Red
                                    width: 1
                                    capStyle: Qt.DashLine
                                }

                                // -2 threshold line
                                LineSeries {
                                    id: zscoreThresholdMinus2
                                    name: "-2σ"
                                    color: Material.Green
                                    width: 1
                                    capStyle: Qt.DashLine
                                }

                                // Zero line
                                LineSeries {
                                    id: zscoreZeroLine
                                    name: "0"
                                    color: Qt.rgba(1, 1, 1, 0.3)
                                    width: 1
                                    capStyle: Qt.DashLine
                                }
                            }

                            // Hover overlay for tooltip and zoom
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                propagateComposedEvents: true

                                property point panStart
                                property var panXMin
                                property var panXMax
                                property real panYMin
                                property real panYMax

                                onPositionChanged: function(mouse) {
                                    // Handle panning
                                    if (pressedButtons & Qt.RightButton) {
                                        var dx = mouse.x - panStart.x
                                        var dy = mouse.y - panStart.y

                                        var xRange = panXMax.getTime() - panXMin.getTime()
                                        var yRange = panYMax - panYMin

                                        var xShift = -(dx / width) * xRange
                                        var yShift = (dy / height) * yRange

                                        zscoreAxisX.min = new Date(panXMin.getTime() + xShift)
                                        zscoreAxisX.max = new Date(panXMax.getTime() + xShift)
                                        zscoreAxisY.min = panYMin + yShift
                                        zscoreAxisY.max = panYMax + yShift
                                        return
                                    }

                                    // Handle tooltip
                                    var timestamps = analysisModel.zscoreTimestamps
                                    var values = analysisModel.zscoreValues

                                    if (timestamps.length === 0 || values.length === 0) {
                                        zscoreTooltip.visible = false
                                        return
                                    }

                                    // Map mouse X position to timestamp (milliseconds)
                                    var chartWidth = zscoreChart.width
                                    var timeRange = zscoreAxisX.max.getTime() - zscoreAxisX.min.getTime()
                                    var mouseTimeMs = zscoreAxisX.min.getTime() + (mouse.x / chartWidth) * timeRange

                                    // Binary search for nearest timestamp
                                    var idx = findNearestIndex(timestamps, mouseTimeMs)

                                    if (idx >= 0) {
                                        var date = new Date(timestamps[idx])
                                        zscoreTooltip.x = mouse.x + 10
                                        zscoreTooltip.y = mouse.y - 40
                                        zscoreTooltip.text = Qt.formatDateTime(date, "MMM dd hh:mm") + "\nZ-Score: " + values[idx].toFixed(2)
                                        zscoreTooltip.visible = true
                                    }
                                }

                                onPressed: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        panStart = Qt.point(mouse.x, mouse.y)
                                        panXMin = zscoreAxisX.min
                                        panXMax = zscoreAxisX.max
                                        panYMin = zscoreAxisY.min
                                        panYMax = zscoreAxisY.max
                                    }
                                }

                                onWheel: function(wheel) {
                                    if (wheel.modifiers & Qt.ShiftModifier) {
                                        // Shift + Wheel: Zoom X-axis
                                        zoomDateTimeAxis(zscoreAxisX, wheel.angleDelta.y, wheel.x, width)
                                        wheel.accepted = true
                                    } else if (wheel.modifiers & Qt.ControlModifier) {
                                        // Ctrl + Wheel: Zoom Y-axis
                                        zoomValueAxis(zscoreAxisY, wheel.angleDelta.y, wheel.y, height)
                                        wheel.accepted = true
                                    } else {
                                        // No modifier: Page scroll
                                        wheel.accepted = false
                                    }
                                }

                                onDoubleClicked: function(mouse) {
                                    // Reset zoom
                                    if (zscoreChart.origXMin) {
                                        zscoreAxisX.min = zscoreChart.origXMin
                                        zscoreAxisX.max = zscoreChart.origXMax
                                        zscoreAxisY.min = zscoreChart.origYMin
                                        zscoreAxisY.max = zscoreChart.origYMax
                                    }
                                }

                                onExited: {
                                    zscoreTooltip.visible = false
                                }
                            }

                            // Tooltip
                            Rectangle {
                                id: zscoreTooltip
                                visible: false
                                width: zscoreTooltipText.width + 16
                                height: zscoreTooltipText.height + 12
                                color: Qt.rgba(0.1, 0.1, 0.1, 0.95)
                                radius: 4
                                border.width: 1
                                border.color: "#CE93D8"
                                z: 1000

                                property alias text: zscoreTooltipText.text

                                Label {
                                    id: zscoreTooltipText
                                    anchors.centerIn: parent
                                    color: Material.foreground
                                    font.pixelSize: 11
                                }
                            }

                        }
                    }
                    }

                    // Spread Chart (High-Low with BarSeries)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.chartHeight
                    color: Qt.rgba(1, 1, 1, 0.05)
                    radius: 8
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.12)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Label {
                            text: "Normalized Spread (Base=100)"
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: Material.foreground
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            GraphsView {
                                id: spreadChart
                                anchors.fill: parent

                                // Store original axis ranges for reset
                                property var origXMin
                                property var origXMax
                                property real origYMin
                                property real origYMax

                                theme: GraphsTheme {
                                    colorScheme: GraphsTheme.ColorScheme.Dark

                                    // Grid lines
                                    grid.mainColor: Qt.rgba(1, 1, 1, 0.1)
                                    grid.subColor: Qt.rgba(1, 1, 1, 0.05)

                                    // Axis label TEXT color (white)
                                    labelTextColor: Material.foreground

                                    // Axis LINE colors (subtle white)
                                    axisX.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                    axisY.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                }

                                axisX: DateTimeAxis {
                                    id: spreadAxisX
                                    labelFormat: "MMM dd"
                                }

                                axisY: ValueAxis {
                                    id: spreadAxisY
                                    labelFormat: "%.2f"
                                }

                                // High-Low range using AreaSeries (filled area)
                                LineSeries {
                                    id: spreadHighLine
                                    name: "High"
                                    visible: false  // Only used for AreaSeries boundary
                                }

                                LineSeries {
                                    id: spreadLowLine
                                    name: "Low"
                                    visible: false  // Only used for AreaSeries boundary
                                }

                                AreaSeries {
                                    id: spreadArea
                                    name: "High-Low Range"
                                    upperSeries: spreadHighLine
                                    lowerSeries: spreadLowLine
                                    color: Qt.rgba(0.8, 0.8, 0.8, 0.3)
                                    borderColor: Qt.rgba(0.9, 0.9, 0.9, 0.6)
                                    borderWidth: 2
                                }

                                // Close line
                                LineSeries {
                                    id: spreadCloseLine
                                    name: "Close"
                                    color: "#90CAF9"
                                    width: 2
                                }
                            }

                            // Hover overlay for tooltip and zoom
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                propagateComposedEvents: true

                                property point panStart
                                property var panXMin
                                property var panXMax
                                property real panYMin
                                property real panYMax

                                onPositionChanged: function(mouse) {
                                    // Handle panning
                                    if (pressedButtons & Qt.RightButton) {
                                        var dx = mouse.x - panStart.x
                                        var dy = mouse.y - panStart.y

                                        var xRange = panXMax.getTime() - panXMin.getTime()
                                        var yRange = panYMax - panYMin

                                        var xShift = -(dx / width) * xRange
                                        var yShift = (dy / height) * yRange

                                        spreadAxisX.min = new Date(panXMin.getTime() + xShift)
                                        spreadAxisX.max = new Date(panXMax.getTime() + xShift)
                                        spreadAxisY.min = panYMin + yShift
                                        spreadAxisY.max = panYMax + yShift
                                        return
                                    }

                                    // Handle tooltip
                                    var timestamps = analysisModel.spreadTimestamps
                                    var opens = analysisModel.spreadOpen
                                    var highs = analysisModel.spreadHigh
                                    var lows = analysisModel.spreadLow
                                    var closes = analysisModel.spreadClose

                                    if (timestamps.length === 0) {
                                        spreadTooltip.visible = false
                                        return
                                    }

                                    // Map mouse X position to timestamp (milliseconds)
                                    var chartWidth = spreadChart.width
                                    var timeRange = spreadAxisX.max.getTime() - spreadAxisX.min.getTime()
                                    var mouseTimeMs = spreadAxisX.min.getTime() + (mouse.x / chartWidth) * timeRange

                                    // Binary search for nearest timestamp
                                    var idx = findNearestIndex(timestamps, mouseTimeMs)

                                    if (idx >= 0) {
                                        var date = new Date(timestamps[idx])
                                        spreadTooltip.x = mouse.x + 10
                                        spreadTooltip.y = mouse.y - 70
                                        spreadTooltip.text = Qt.formatDateTime(date, "MMM dd hh:mm") +
                                                          "\nO: " + opens[idx].toFixed(2) +
                                                          "\nH: " + highs[idx].toFixed(2) +
                                                          "\nL: " + lows[idx].toFixed(2) +
                                                          "\nC: " + closes[idx].toFixed(2)
                                        spreadTooltip.visible = true
                                    }
                                }

                                onPressed: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        panStart = Qt.point(mouse.x, mouse.y)
                                        panXMin = spreadAxisX.min
                                        panXMax = spreadAxisX.max
                                        panYMin = spreadAxisY.min
                                        panYMax = spreadAxisY.max
                                    }
                                }

                                onWheel: function(wheel) {
                                    if (wheel.modifiers & Qt.ShiftModifier) {
                                        // Shift + Wheel: Zoom X-axis
                                        zoomDateTimeAxis(spreadAxisX, wheel.angleDelta.y, wheel.x, width)
                                        wheel.accepted = true
                                    } else if (wheel.modifiers & Qt.ControlModifier) {
                                        // Ctrl + Wheel: Zoom Y-axis
                                        zoomValueAxis(spreadAxisY, wheel.angleDelta.y, wheel.y, height)
                                        wheel.accepted = true
                                    } else {
                                        // No modifier: Page scroll
                                        wheel.accepted = false
                                    }
                                }

                                onDoubleClicked: function(mouse) {
                                    // Reset zoom
                                    if (spreadChart.origXMin) {
                                        spreadAxisX.min = spreadChart.origXMin
                                        spreadAxisX.max = spreadChart.origXMax
                                        spreadAxisY.min = spreadChart.origYMin
                                        spreadAxisY.max = spreadChart.origYMax
                                    }
                                }

                                onExited: {
                                    spreadTooltip.visible = false
                                }
                            }

                            // Tooltip
                            Rectangle {
                                id: spreadTooltip
                                visible: false
                                width: spreadTooltipText.width + 16
                                height: spreadTooltipText.height + 12
                                color: Qt.rgba(0.1, 0.1, 0.1, 0.95)
                                radius: 4
                                border.width: 1
                                border.color: "#90CAF9"
                                z: 1000

                                property alias text: spreadTooltipText.text

                                Label {
                                    id: spreadTooltipText
                                    anchors.centerIn: parent
                                    color: Material.foreground
                                    font.pixelSize: 11
                                }
                            }

                        }
                    }
                    }

                    // Rolling Correlation Chart
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.chartHeight
                    color: Qt.rgba(1, 1, 1, 0.05)
                    radius: 8
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.12)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Label {
                            text: "Rolling Correlation (20-period)"
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: Material.foreground
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            GraphsView {
                                id: corrChart
                                anchors.fill: parent

                                // Store original axis ranges for reset
                                property var origXMin
                                property var origXMax
                                property real origYMin
                                property real origYMax

                                theme: GraphsTheme {
                                    colorScheme: GraphsTheme.ColorScheme.Dark

                                    // Grid lines
                                    grid.mainColor: Qt.rgba(1, 1, 1, 0.1)
                                    grid.subColor: Qt.rgba(1, 1, 1, 0.05)

                                    // Axis label TEXT color (white)
                                    labelTextColor: Material.foreground

                                    // Axis LINE colors (subtle white)
                                    axisX.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                    axisY.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                }

                                axisX: DateTimeAxis {
                                    id: corrAxisX
                                    labelFormat: "MMM dd"
                                }

                                axisY: ValueAxis {
                                    id: corrAxisY
                                    min: -1.0
                                    max: 1.0
                                    labelFormat: "%.2f"
                                }

                                LineSeries {
                                    id: rollingCorrSeries
                                    name: "Rolling Correlation"
                                    color: "#66BB6A"  // Green
                                    width: 2
                                }
                            }

                            // Hover overlay for tooltip and zoom
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                propagateComposedEvents: true

                                property point panStart
                                property var panXMin
                                property var panXMax
                                property real panYMin
                                property real panYMax

                                onPositionChanged: function(mouse) {
                                    // Handle panning
                                    if (pressedButtons & Qt.RightButton) {
                                        var dx = mouse.x - panStart.x
                                        var dy = mouse.y - panStart.y

                                        var xRange = panXMax.getTime() - panXMin.getTime()
                                        var yRange = panYMax - panYMin

                                        var xShift = -(dx / width) * xRange
                                        var yShift = (dy / height) * yRange

                                        corrAxisX.min = new Date(panXMin.getTime() + xShift)
                                        corrAxisX.max = new Date(panXMax.getTime() + xShift)
                                        corrAxisY.min = panYMin + yShift
                                        corrAxisY.max = panYMax + yShift
                                        return
                                    }

                                    // Handle tooltip
                                    var timestamps = analysisModel.rollingCorrTimestamps
                                    var values = analysisModel.rollingCorrValues

                                    if (timestamps.length === 0 || values.length === 0) {
                                        corrTooltip.visible = false
                                        return
                                    }

                                    // Map mouse X position to timestamp (milliseconds)
                                    var chartWidth = corrChart.width
                                    var timeRange = corrAxisX.max.getTime() - corrAxisX.min.getTime()
                                    var mouseTimeMs = corrAxisX.min.getTime() + (mouse.x / chartWidth) * timeRange

                                    // Binary search for nearest timestamp
                                    var idx = findNearestIndex(timestamps, mouseTimeMs)

                                    if (idx >= 0) {
                                        var date = new Date(timestamps[idx])
                                        corrTooltip.x = mouse.x + 10
                                        corrTooltip.y = mouse.y - 40
                                        corrTooltip.text = Qt.formatDateTime(date, "MMM dd hh:mm") + "\nCorrelation: " + values[idx].toFixed(4)
                                        corrTooltip.visible = true
                                    }
                                }

                                onPressed: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        panStart = Qt.point(mouse.x, mouse.y)
                                        panXMin = corrAxisX.min
                                        panXMax = corrAxisX.max
                                        panYMin = corrAxisY.min
                                        panYMax = corrAxisY.max
                                    }
                                }

                                onWheel: function(wheel) {
                                    if (wheel.modifiers & Qt.ShiftModifier) {
                                        // Shift + Wheel: Zoom X-axis
                                        zoomDateTimeAxis(corrAxisX, wheel.angleDelta.y, wheel.x, width)
                                        wheel.accepted = true
                                    } else if (wheel.modifiers & Qt.ControlModifier) {
                                        // Ctrl + Wheel: Zoom Y-axis
                                        zoomValueAxis(corrAxisY, wheel.angleDelta.y, wheel.y, height)
                                        wheel.accepted = true
                                    } else {
                                        // No modifier: Page scroll
                                        wheel.accepted = false
                                    }
                                }

                                onDoubleClicked: function(mouse) {
                                    // Reset zoom
                                    if (corrChart.origXMin) {
                                        corrAxisX.min = corrChart.origXMin
                                        corrAxisX.max = corrChart.origXMax
                                        corrAxisY.min = corrChart.origYMin
                                        corrAxisY.max = corrChart.origYMax
                                    }
                                }

                                onExited: {
                                    corrTooltip.visible = false
                                }
                            }

                            // Tooltip
                            Rectangle {
                                id: corrTooltip
                                visible: false
                                width: corrTooltipText.width + 16
                                height: corrTooltipText.height + 12
                                color: Qt.rgba(0.1, 0.1, 0.1, 0.95)
                                radius: 4
                                border.width: 1
                                border.color: "#66BB6A"
                                z: 1000

                                property alias text: corrTooltipText.text

                                Label {
                                    id: corrTooltipText
                                    anchors.centerIn: parent
                                    color: Material.foreground
                                    font.pixelSize: 11
                                }
                            }

                        }
                    }
                    }

                    // Beta Evolution Chart
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.chartHeight
                    color: Qt.rgba(1, 1, 1, 0.05)
                    radius: 8
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.12)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Label {
                            text: "Beta Evolution with 95% CI"
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: Material.foreground
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            GraphsView {
                                id: betaChart
                                anchors.fill: parent

                                // Store original axis ranges for reset
                                property var origXMin
                                property var origXMax
                                property real origYMin
                                property real origYMax

                                theme: GraphsTheme {
                                    colorScheme: GraphsTheme.ColorScheme.Dark

                                    // Grid lines
                                    grid.mainColor: Qt.rgba(1, 1, 1, 0.1)
                                    grid.subColor: Qt.rgba(1, 1, 1, 0.05)

                                    // Axis label TEXT color (white)
                                    labelTextColor: Material.foreground

                                    // Axis LINE colors (subtle white)
                                    axisX.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                    axisY.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                }

                                axisX: DateTimeAxis {
                                    id: betaAxisX
                                    labelFormat: "MMM dd"
                                }

                                axisY: ValueAxis {
                                    id: betaAxisY
                                    labelFormat: "%.2f"
                                }

                                // CI boundary lines (invisible, used by AreaSeries)
                                LineSeries {
                                    id: betaCiUpperLine
                                    name: "CI Upper"
                                    visible: false
                                }

                                LineSeries {
                                    id: betaCiLowerLine
                                    name: "CI Lower"
                                    visible: false
                                }

                                // Confidence interval area
                                AreaSeries {
                                    id: betaCiArea
                                    name: "95% Confidence Interval"
                                    upperSeries: betaCiUpperLine
                                    lowerSeries: betaCiLowerLine
                                    color: Qt.rgba(0.5, 0.5, 0.5, 0.2)
                                    borderColor: Qt.rgba(0.7, 0.7, 0.7, 0.3)
                                    borderWidth: 1
                                }

                                // Beta line (invisible, used for duplicate data)
                                LineSeries {
                                    id: betaLine
                                    name: "Beta Line"
                                    visible: false
                                }

                                // Reference line at beta = 1.0
                                LineSeries {
                                    id: betaRefLine
                                    name: "Beta = 1.0"
                                    color: Qt.rgba(1, 1, 1, 0.3)
                                    width: 1
                                    capStyle: Qt.DashLine
                                }

                                // Main beta series (on top)
                                LineSeries {
                                    id: betaSeries
                                    name: "Beta"
                                    color: "#EF5350"  // Red
                                    width: 2
                                }
                            }

                            // Hover overlay for tooltip and zoom
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                propagateComposedEvents: true

                                property point panStart
                                property var panXMin
                                property var panXMax
                                property real panYMin
                                property real panYMax

                                onPositionChanged: function(mouse) {
                                    // Handle panning
                                    if (pressedButtons & Qt.RightButton) {
                                        var dx = mouse.x - panStart.x
                                        var dy = mouse.y - panStart.y

                                        var xRange = panXMax.getTime() - panXMin.getTime()
                                        var yRange = panYMax - panYMin

                                        var xShift = -(dx / width) * xRange
                                        var yShift = (dy / height) * yRange

                                        betaAxisX.min = new Date(panXMin.getTime() + xShift)
                                        betaAxisX.max = new Date(panXMax.getTime() + xShift)
                                        betaAxisY.min = panYMin + yShift
                                        betaAxisY.max = panYMax + yShift
                                        return
                                    }

                                    // Handle tooltip
                                    var timestamps = analysisModel.betaTimestamps
                                    var values = analysisModel.betaValues
                                    var ciUpper = analysisModel.betaCiUpper
                                    var ciLower = analysisModel.betaCiLower

                                    if (timestamps.length === 0 || values.length === 0) {
                                        betaTooltip.visible = false
                                        return
                                    }

                                    // Map mouse X position to timestamp (milliseconds)
                                    var chartWidth = betaChart.width
                                    var timeRange = betaAxisX.max.getTime() - betaAxisX.min.getTime()
                                    var mouseTimeMs = betaAxisX.min.getTime() + (mouse.x / chartWidth) * timeRange

                                    // Binary search for nearest timestamp
                                    var idx = findNearestIndex(timestamps, mouseTimeMs)

                                    if (idx >= 0) {
                                        var date = new Date(timestamps[idx])
                                        betaTooltip.x = mouse.x + 10
                                        betaTooltip.y = mouse.y - 60
                                        betaTooltip.text = Qt.formatDateTime(date, "MMM dd hh:mm") +
                                                          "\nBeta: " + values[idx].toFixed(4) +
                                                          "\nCI: [" + ciLower[idx].toFixed(4) + ", " + ciUpper[idx].toFixed(4) + "]"
                                        betaTooltip.visible = true
                                    }
                                }

                                onPressed: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        panStart = Qt.point(mouse.x, mouse.y)
                                        panXMin = betaAxisX.min
                                        panXMax = betaAxisX.max
                                        panYMin = betaAxisY.min
                                        panYMax = betaAxisY.max
                                    }
                                }

                                onWheel: function(wheel) {
                                    if (wheel.modifiers & Qt.ShiftModifier) {
                                        // Shift + Wheel: Zoom X-axis
                                        zoomDateTimeAxis(betaAxisX, wheel.angleDelta.y, wheel.x, width)
                                        wheel.accepted = true
                                    } else if (wheel.modifiers & Qt.ControlModifier) {
                                        // Ctrl + Wheel: Zoom Y-axis
                                        zoomValueAxis(betaAxisY, wheel.angleDelta.y, wheel.y, height)
                                        wheel.accepted = true
                                    } else {
                                        // No modifier: Page scroll
                                        wheel.accepted = false
                                    }
                                }

                                onDoubleClicked: function(mouse) {
                                    // Reset zoom
                                    if (betaChart.origXMin) {
                                        betaAxisX.min = betaChart.origXMin
                                        betaAxisX.max = betaChart.origXMax
                                        betaAxisY.min = betaChart.origYMin
                                        betaAxisY.max = betaChart.origYMax
                                    }
                                }

                                onExited: {
                                    betaTooltip.visible = false
                                }
                            }

                            // Tooltip
                            Rectangle {
                                id: betaTooltip
                                visible: false
                                width: betaTooltipText.width + 16
                                height: betaTooltipText.height + 12
                                color: Qt.rgba(0.1, 0.1, 0.1, 0.95)
                                radius: 4
                                border.width: 1
                                border.color: "#EF5350"
                                z: 1000

                                property alias text: betaTooltipText.text

                                Label {
                                    id: betaTooltipText
                                    anchors.centerIn: parent
                                    color: Material.foreground
                                    font.pixelSize: 11
                                }
                            }

                        }
                    }
                    }

                    // Spread Volatility Chart
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.chartHeight
                    color: Qt.rgba(1, 1, 1, 0.05)
                    radius: 8
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.12)

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Label {
                            text: "Spread Volatility Evolution (Rolling 20-period, Annualized)"
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: Material.foreground
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            GraphsView {
                                id: volatilityChart
                                anchors.fill: parent

                                // Store original axis ranges for reset
                                property var origXMin
                                property var origXMax
                                property real origYMin
                                property real origYMax

                                theme: GraphsTheme {
                                    colorScheme: GraphsTheme.ColorScheme.Dark
                                    grid.mainColor: Qt.rgba(1, 1, 1, 0.1)
                                    grid.subColor: Qt.rgba(1, 1, 1, 0.05)
                                    labelTextColor: Material.foreground
                                    axisX.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                    axisY.mainColor: Qt.rgba(1, 1, 1, 0.3)
                                }

                                axisX: DateTimeAxis {
                                    id: volatilityAxisX
                                    labelFormat: "MMM dd"
                                }

                                axisY: ValueAxis {
                                    id: volatilityAxisY
                                    labelFormat: "%.1f%%"
                                }

                                LineSeries {
                                    id: volatilitySeries
                                    name: "Volatility"
                                    color: "#FF9800"  // Orange
                                    width: 2
                                }
                            }

                            // Mouse area for interaction
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                propagateComposedEvents: true

                                property point panStart
                                property var panXMin
                                property var panXMax
                                property real panYMin
                                property real panYMax

                                onPositionChanged: function(mouse) {
                                    if (pressedButtons & Qt.RightButton) {
                                        var dx = mouse.x - panStart.x
                                        var dy = mouse.y - panStart.y

                                        var xRange = panXMax.getTime() - panXMin.getTime()
                                        var yRange = panYMax - panYMin

                                        var xShift = -(dx / width) * xRange
                                        var yShift = (dy / height) * yRange

                                        volatilityAxisX.min = new Date(panXMin.getTime() + xShift)
                                        volatilityAxisX.max = new Date(panXMax.getTime() + xShift)
                                        volatilityAxisY.min = panYMin + yShift
                                        volatilityAxisY.max = panYMax + yShift
                                        return
                                    }
                                }

                                onPressed: function(mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        panStart = Qt.point(mouse.x, mouse.y)
                                        panXMin = volatilityAxisX.min
                                        panXMax = volatilityAxisX.max
                                        panYMin = volatilityAxisY.min
                                        panYMax = volatilityAxisY.max
                                    }
                                }

                                onWheel: function(wheel) {
                                    if (wheel.modifiers & Qt.ShiftModifier) {
                                        zoomDateTimeAxis(volatilityAxisX, wheel.angleDelta.y, wheel.x, width)
                                        wheel.accepted = true
                                    } else if (wheel.modifiers & Qt.ControlModifier) {
                                        zoomValueAxis(volatilityAxisY, wheel.angleDelta.y, wheel.y, height)
                                        wheel.accepted = true
                                    } else {
                                        wheel.accepted = false
                                    }
                                }

                                onDoubleClicked: function(mouse) {
                                    if (volatilityChart.origXMin) {
                                        volatilityAxisX.min = volatilityChart.origXMin
                                        volatilityAxisX.max = volatilityChart.origXMax
                                        volatilityAxisY.min = volatilityChart.origYMin
                                        volatilityAxisY.max = volatilityChart.origYMax
                                    }
                                }
                            }
                        }
                    }
                    }
                }
            }

            // Custom scrollbar
            Rectangle {
                id: scrollbar
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 8
                color: Qt.rgba(1, 1, 1, 0.05)
                radius: 4
                visible: chartFlickable.contentHeight > chartFlickable.height
                opacity: scrollbarArea.containsMouse || scrollbarHandle.pressed ? 1.0 : 0.4

                Behavior on opacity {
                    NumberAnimation { duration: 200 }
                }

                // Scrollbar handle
                Rectangle {
                    id: scrollbarHandle
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: parent.width - 2
                    radius: 3
                    color: Material.accent

                    property bool pressed: false

                    height: Math.max(30, chartFlickable.height * (chartFlickable.height / chartFlickable.contentHeight))
                    y: chartFlickable.contentY * (chartFlickable.height / chartFlickable.contentHeight)

                    MouseArea {
                        id: scrollbarArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor

                        property real pressY
                        property real pressContentY

                        onPressed: function(mouse) {
                            scrollbarHandle.pressed = true
                            pressY = mouse.y
                            pressContentY = chartFlickable.contentY
                        }

                        onPositionChanged: function(mouse) {
                            if (pressed) {
                                var delta = mouse.y - pressY
                                var ratio = chartFlickable.contentHeight / chartFlickable.height
                                chartFlickable.contentY = Math.max(0, Math.min(
                                    chartFlickable.contentHeight - chartFlickable.height,
                                    pressContentY + delta * ratio
                                ))
                            }
                        }

                        onReleased: {
                            scrollbarHandle.pressed = false
                        }
                    }
                }
            }
        }

        // Empty state
        Label {
            text: "Select a pair from Watchlist or Discovery to begin analysis"
            font.pixelSize: 16
            opacity: 0.5
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !analysisModel.isLoading && analysisModel.currentPair === ""
        }

        // Loading state
        BusyIndicator {
            running: analysisModel.isLoading
            Layout.alignment: Qt.AlignHCenter
            visible: analysisModel.isLoading
        }
    }

    function loadPair(coin1, coin2) {
        errorLabel.visible = false

        // Reset to default settings when loading from outside
        timeframeCombo.currentIndex = 1  // 1hour

        analysisModel.loadPair(coin1, coin2, timeframeCombo.currentText)
    }

    function loadPairWithSettings(coin1, coin2) {
        errorLabel.visible = false
        analysisModel.loadPair(coin1, coin2, timeframeCombo.currentText)
    }
}
