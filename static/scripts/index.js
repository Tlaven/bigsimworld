document.addEventListener('DOMContentLoaded', () => {
    // 创建EventSource实例，连接到服务器端点
    var eventSource = new EventSource('/api');
    var myChart = echarts.init(document.getElementById('myChart'));

    // 监听message事件，当接收到服务器发送的数据时触发
    eventSource.onmessage = function(event) {
        var data = JSON.parse(event.data);
        populateList(data.individual_list);
        myChart.setOption(data.chart_options);
    };

    // Populate the individual_column_list with data
    function populateList(data) {
        const listContainer = document.querySelector('.individual_column_list');
        listContainer.innerHTML = '';
        data.forEach(item => {
            const listItem = document.createElement('div');
            listItem.innerHTML = `
                <h3>${item.name}    ${item.gender}</h3>
                <p>${item.age}</p>
                <p>${item.wealth}</p>
            `;
            listContainer.appendChild(listItem);
        });
    }

    // Add event listeners to chart buttons
    document.getElementById('chart1-button').addEventListener('click', () => {
        createChart(chart1Data, chart1Labels);
    });

    document.getElementById('chart2-button').addEventListener('click', () => {
        createChart(chart2Data, chart2Labels);
    });
});