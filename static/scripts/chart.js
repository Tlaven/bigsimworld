document.addEventListener('DOMContentLoaded', () => {
    // 初始化echarts实例
    var myChart = echarts.init(document.getElementById('myChart'));
    // 创建EventSource实例，连接到服务器端点
    var eventSource = new EventSource('/api');

    // 监听message事件，当接收到服务器发送的数据时触发
    eventSource.onmessage = function(event) {
        // 假设服务器发送的数据是JSON格式的字符串
        var data = JSON.parse(event.data);
        myChart.setOption(data.chart_options);
    };

    // 监听可能发生的错误
    eventSource.onerror = function(error) {
        console.error('EventSource failed:', error);
    };
});