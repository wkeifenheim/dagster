import {ColorsWIP} from '@dagster-io/ui';
import {ActiveElement, TimeUnit, TooltipItem} from 'chart.js';
import * as React from 'react';
import {Line} from 'react-chartjs-2';

import {InstigationTickStatus} from '../types/globalTypes';

import {
  TickHistoryQuery_instigationStateOrError_InstigationState_nextTick,
  TickHistoryQuery_instigationStateOrError_InstigationState_ticks,
} from './types/TickHistoryQuery';

type FutureTick = TickHistoryQuery_instigationStateOrError_InstigationState_nextTick;
type InstigationTick = TickHistoryQuery_instigationStateOrError_InstigationState_ticks;

const COLOR_MAP = {
  [InstigationTickStatus.SUCCESS]: ColorsWIP.Blue500,
  [InstigationTickStatus.FAILURE]: ColorsWIP.Red500,
  [InstigationTickStatus.STARTED]: ColorsWIP.Gray400,
  [InstigationTickStatus.SKIPPED]: ColorsWIP.Yellow500,
};

const REFRESH_INTERVAL = 100;

export const LiveTickTimeline: React.FC<{
  ticks: InstigationTick[];
  nextTick: FutureTick | null;
  onHoverTick: (InstigationTick?: any) => void;
  onSelectTick: (InstigationTick?: any) => void;
}> = ({ticks, nextTick, onHoverTick, onSelectTick}) => {
  const [now, setNow] = React.useState<number>(Date.now());
  const [graphNow, setGraphNow] = React.useState<number>(Date.now());
  const [isPaused, setPaused] = React.useState<boolean>(false);
  React.useEffect(() => {
    const interval = setInterval(() => {
      !isPaused && setNow(Date.now());
    }, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  });

  React.useEffect(() => {
    if (!isPaused && (!nextTick || now < 1000 * nextTick.timestamp)) {
      setGraphNow(now);
    }
  }, [isPaused, nextTick, now]);

  const isAtFutureTick = nextTick && 1000 * nextTick.timestamp <= now;
  const PULSE_DURATION = 2000;
  const nextTickRadius = isAtFutureTick
    ? 4 + Math.sin((2 * Math.PI * (now % PULSE_DURATION)) / PULSE_DURATION)
    : 3;

  const tickData = ticks.map((tick) => ({x: 1000 * tick.timestamp, y: 0}));
  const tickColors = ticks.map((tick) => COLOR_MAP[tick.status]);
  const tickRadii = Array(ticks.length).fill(3);

  if (nextTick) {
    tickData.push({x: 1000 * nextTick.timestamp, y: 0});
    tickColors.push(ColorsWIP.Gray200);
    tickRadii.push(nextTickRadius);
  }

  const graphData = {
    labels: ['ticks'],
    datasets: [
      {
        label: 'now',
        data: [
          {x: graphNow - 60000 * 10, y: 0},
          {x: graphNow, y: 0},
        ],
        borderColor: ColorsWIP.Gray100,
        borderWidth: 1,
        pointBorderWidth: 2,
        pointBorderColor: ColorsWIP.Gray200,
        pointRadius: 1,
        pointHoverRadius: 1,
      },
      {
        label: 'ticks',
        data: tickData,
        borderColor: ColorsWIP.Gray100,
        borderWidth: 0,
        backgroundColor: 'rgba(0,0,0,0)',
        pointBackgroundColor: 'rgba(0,0,0,0)',
        pointBorderWidth: 2,
        pointBorderColor: tickColors,
        pointRadius: tickRadii,
        pointHoverBorderWidth: 2,
        pointHoverRadius: 5,
        pointHoverBorderColor: tickColors,
      },
    ],
  };

  const options = {
    animation: {
      duration: 0,
    },

    scales: {
      y: {id: 'y', display: false, grid: {display: false}, title: {display: false}},
      x: {
        id: 'x',
        type: 'time',
        title: {
          display: false,
        },
        grid: {display: true},
        bounds: 'ticks',
        min: graphNow - 60000 * 5, // 5 minutes ago
        max: graphNow + 60000, // 1 minute from now
        time: {
          minUnit: 'minute' as TimeUnit,
        },
      },
    },

    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        displayColors: false,
        callbacks: {
          label: function (tooltipItem: TooltipItem<any>) {
            if (!tooltipItem.datasetIndex) {
              // this is the current time
              return 'Current time';
            }
            if (tooltipItem.dataIndex === undefined) {
              return '';
            }
            if (tooltipItem.dataIndex === ticks.length) {
              // This is the future tick
              return '';
            }
            const tick = ticks[tooltipItem.dataIndex];
            if (tick.status === InstigationTickStatus.SKIPPED && tick.skipReason) {
              return tick.skipReason;
            }
            if (tick.status === InstigationTickStatus.SUCCESS && tick.runIds.length) {
              return tick.runIds;
            }
            if (tick.status === InstigationTickStatus.SUCCESS && tick.originRunIds) {
              return tick.originRunIds;
            }
            if (tick.status === InstigationTickStatus.FAILURE && tick.error?.message) {
              return tick.error.message;
            }
            return '';
          },
        },
      },
    },

    onClick: (_event: MouseEvent, activeElements: any[]) => {
      if (!activeElements.length) {
        return;
      }
      const [item] = activeElements;
      if (item.datasetIndex === undefined || item.index === undefined) {
        return;
      }
      const tick = ticks[item.index];
      onSelectTick(tick);
    },

    onHover: (event: MouseEvent, elements: ActiveElement[]) => {
      if (event?.target instanceof HTMLElement) {
        event.target.style.cursor = elements.length ? 'pointer' : 'default';
      }
      if (elements.length && !isPaused) {
        setPaused(true);
        const [element] = elements.filter(
          (x) => x.datasetIndex === 1 && x.index !== undefined && x.index < ticks.length,
        );
        if (!element) {
          return;
        }
        const tick = ticks[element.index];
        onHoverTick(tick);
      } else if (!elements.length && isPaused) {
        setPaused(false);
        onHoverTick(undefined);
      }
    },
  };

  return <Line type="line" data={graphData} height={30} options={options} key="100%" />;
};
