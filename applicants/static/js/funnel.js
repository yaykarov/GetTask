function bar_color(datum, index) {
    return datum.color;
}

function readable_interval(seconds) {
    let seconds_in_minute = 60;
    let seconds_in_hour = seconds_in_minute * 60;
    let seconds_in_day = seconds_in_hour * 24;

    let days = Math.floor(seconds / seconds_in_day);
    var remainder = seconds % seconds_in_day;
    let hours = Math.floor(remainder / seconds_in_hour);
    remainder = remainder % seconds_in_hour;
    let minutes = Math.floor(remainder / seconds_in_minute);
    remainder = remainder % seconds_in_minute;

    var result = '';
    if (days > 0) {
        result += (days.toString() + 'д ');
    }
    if (days > 0 || hours > 0) {
        result += (hours.toString() + 'ч ');
    }
    result += (minutes.toString() + 'м');
    if (days == 0) {
        result += (' ' + remainder.toString() + 'с');
    }

    return result;
}

function render_gantt(root, viewport, funnel_data) {
    overall_seconds = d3.max(
        funnel_data,
        function(datum) {
            if (datum.need_gantt) {
                return datum.begin + datum.seconds;
            }
            return 0;
        }
    );
    if (overall_seconds < 1) {
        overall_seconds = 1;
    }

    let barHeight = 5;
    let textOffsetX = 4;
    let textOffsetY = 4;

    let barWidth = function(datum, index) {
        if (!datum.need_gantt) {
            return 0;
        }
        if (index == funnel_data.length - 1) {
            return 0;
        }
        return Math.max(
            1,
            Math.max(datum.seconds, 1) * viewport.width / overall_seconds
        );
    }
    let barX = function(datum) {
        if (!datum.need_gantt) {
            return 0;
        }
        return viewport.x + datum.begin * viewport.width / overall_seconds;
    }
    let barY = function(datum, index) {
        return viewport.y + (index + 1) * viewport.height / funnel_data.length - barHeight;
    }

    root.selectAll('rect.gantt-bar')
        .data(funnel_data).enter()
            .append('rect')
            .attr('class', 'gantt-bar')
            .attr('x', barX)
            .attr('y', barY)
            .attr('width', barWidth)
            .attr('height', barHeight)
            .attr('fill', bar_color);

    let barTextX = function(datum, index) {
        return barX(datum, index) + textOffsetX;
    }
    let barTextY = function(datum, index) {
        return barY(datum, index) - textOffsetY;
    }
    let barText = function(datum) {
        if (!datum.need_gantt) {
            return '';
        }
        return readable_interval(datum.seconds);
    }

    root.selectAll('rect.gantt-text')
        .data(funnel_data.slice(0, -1)).enter()
            .append('text')
            .attr('class', 'gantt-text')
            .attr('x', barTextX)
            .attr('y', barTextY)
            .text(barText);
}

let vBorder = 8;

function render_diagram(root, viewport, funnel_data) {
    let barHeight = viewport.height / funnel_data.length - 2 * vBorder;
    let overallCount = Math.max(funnel_data[0].count, 1);
    let barWidth = function(datum) {
        return Math.max(
            1,
            viewport.width * datum.count / overallCount
        );
    }
    let barX = function(datum) {
        return viewport.x + viewport.width - barWidth(datum);
    }
    let barY = function(datum, index) {
        return index * viewport.height / funnel_data.length + vBorder;
    }
    let url = function(datum, index) {
        return datum.url;
    }

    root.selectAll('rect.diagram-bar')
        .data(funnel_data).enter()
            .append('a')
            .attr('href', url)
            .attr('target', '_blank')
                .append('rect')
                .attr('class', 'diagram-bar')
                .attr('x', barX)
                .attr('y', barY)
                .attr('width', barWidth)
                .attr('height', barHeight)
                .attr('fill', bar_color);

    let barPercentageX = function(datum, index) {
        return barX(datum, index) - vBorder;
    }
    let barPercentageY = function(datum, index) {
        return barY(datum, index) + barHeight / 2;
    }
    let barPercentage = function(datum) {
        return Math.round(
            datum.count * 100 / overallCount
        ).toString() + '%';
    }

    root.selectAll('rect.diagram-percentage')
        .data(funnel_data).enter()
            .append('text')
            .attr('class', 'diagram-percentage')
            .attr('x', barPercentageX)
            .attr('y', barPercentageY)
            .attr('text-anchor', 'end')
            .text(barPercentage);
}

function render_labels(root, viewport, funnel_data) {
    let barHeight = viewport.height / funnel_data.length - 2 * vBorder;
    let labelText = function(datum) {
        return datum.count + ' ' + datum.name;
    }
    let labelX = viewport.x;
    let labelY = function(datum, index) {
        return viewport.y + vBorder + barHeight / 2 +
            index * viewport.height / funnel_data.length;
    }

    root.selectAll('rect.diagram-label')
        .data(funnel_data).enter()
            .append('text')
            .attr('class', 'diagram-label')
            .attr('x', labelX)
            .attr('y', labelY)
            .text(labelText);
}

function render_funnel(selection, width, height, funnel_data) {
    var root = d3.select(selection)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .style('border', '0px solid black');

    let gantt_x = 0.4 * width;
    let gantt_viewport = {
        width: gantt_x,
        height: height,
        x: 0,
        y: 0,
    };
    render_gantt(root, gantt_viewport, funnel_data);

    let diagram_viewport = {
        width: 0.3 * width,
        height: height,
        x: gantt_x + 0.1 * width,
        y: 0
    };
    render_diagram(root, diagram_viewport, funnel_data);

    let label_viewport = {
        width: 0.2 * width,
        height: height,
        x: diagram_viewport.x + diagram_viewport.width + 10,
        y: 0
    };
    render_labels(root, label_viewport, funnel_data);
}

