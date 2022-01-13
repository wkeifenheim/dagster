import {Box, ColorsWIP, IconWIP, IconWrapper, Slider} from '@dagster-io/ui';
import animate from 'amator';
import * as React from 'react';
import styled from 'styled-components/macro';

export interface SVGViewportInteractor {
  onMouseDown(viewport: SVGViewport, event: React.MouseEvent<HTMLDivElement>): void;
  onWheel(viewport: SVGViewport, event: React.MouseEvent<HTMLDivElement>): void;
  render?(viewport: SVGViewport): React.ReactElement<any> | null;
}

interface SVGViewportProps {
  graphWidth: number;
  graphHeight: number;
  backgroundColor?: string;
  interactor: SVGViewportInteractor;
  maxZoom: number;
  maxAutocenterZoom: number;
  onClick?: (event: React.MouseEvent<HTMLDivElement>) => void;
  onDoubleClick?: (event: React.MouseEvent<HTMLDivElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => void;
  children: (
    state: SVGViewportState,
    bounds: {top: number; left: number; bottom: number; right: number},
  ) => React.ReactNode;
}

interface SVGViewportState {
  x: number;
  y: number;
  scale: number;
  minScale: number;
}

interface Point {
  x: number;
  y: number;
}

export const DETAIL_ZOOM = 0.75;
const DEFAULT_ZOOM = 0.75;
const DEFAULT_MAX_AUTOCENTER_ZOOM = 1;

const MIN_AUTOCENTER_ZOOM = 0.17;
const MIN_ZOOM = 0.17;
const BUTTON_INCREMENT = 0.05;

const PanAndZoomInteractor: SVGViewportInteractor = {
  onMouseDown(viewport: SVGViewport, event: React.MouseEvent<HTMLDivElement>) {
    if (viewport._animation) {
      viewport._animation.cancel();
    }

    if (!viewport.element.current) {
      return;
    }

    if (event.target instanceof HTMLElement && event.target.closest('#zoom-slider-container')) {
      return;
    }

    const start = viewport.getOffsetXY(event);
    if (!start) {
      return;
    }

    let lastX: number = start.x;
    let lastY: number = start.y;

    const onMove = (e: MouseEvent) => {
      const offset = viewport.getOffsetXY(e);
      if (!offset) {
        return;
      }

      const delta = {x: offset.x - lastX, y: offset.y - lastY};
      viewport.setState({
        x: viewport.state.x + delta.x,
        y: viewport.state.y + delta.y,
      });
      lastX = offset.x;
      lastY = offset.y;
    };

    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    event.stopPropagation();
  },

  onWheel(viewport: SVGViewport, event: React.WheelEvent<HTMLDivElement>) {
    const cursorPosition = viewport.getOffsetXY(event);
    if (!cursorPosition) {
      return;
    }

    const targetScale = viewport.state.scale * (1 - event.deltaY * 0.0025);
    const scale = Math.max(MIN_ZOOM, Math.min(viewport.getMaxZoom(), targetScale));
    viewport.adjustZoomRelativeToScreenPoint(scale, cursorPosition);
  },

  render(viewport: SVGViewport) {
    return (
      <ZoomSliderContainer id="zoom-slider-container">
        <Box margin={{bottom: 8}}>
          <IconButton
            onClick={() => {
              const x = viewport.element.current!.clientWidth / 2;
              const y = viewport.element.current!.clientHeight / 2;
              const scale = Math.min(
                viewport.getMaxZoom(),
                viewport.state.scale + BUTTON_INCREMENT,
              );
              const adjusted = Math.round((scale + Number.EPSILON) * 100) / 100;
              viewport.adjustZoomRelativeToScreenPoint(adjusted, {x, y});
            }}
          >
            <IconWIP size={24} name="zoom_in" color={ColorsWIP.Gray300} />
          </IconButton>
        </Box>
        <Slider
          vertical
          min={MIN_ZOOM}
          max={viewport.getMaxZoom()}
          stepSize={0.001}
          value={viewport.state.scale}
          labelRenderer={false}
          onChange={(scale: number) => {
            const x = viewport.element.current!.clientWidth / 2;
            const y = viewport.element.current!.clientHeight / 2;
            viewport.adjustZoomRelativeToScreenPoint(scale, {x, y});
          }}
        />
        <Box margin={{top: 8}}>
          <IconButton
            onClick={() => {
              const x = viewport.element.current!.clientWidth / 2;
              const y = viewport.element.current!.clientHeight / 2;
              const scale = Math.max(MIN_ZOOM, viewport.state.scale - BUTTON_INCREMENT);
              viewport.adjustZoomRelativeToScreenPoint(scale, {x, y});
            }}
          >
            <IconWIP size={24} name="zoom_out" color={ColorsWIP.Gray300} />
          </IconButton>
        </Box>
      </ZoomSliderContainer>
    );
  },
};

const IconButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  position: relative;
  left: -4px;

  :focus {
    outline: none;
  }

  ${IconWrapper} {
    transition: background 100ms;
  }

  :focus ${IconWrapper}, :hover ${IconWrapper}, :active ${IconWrapper} {
    background-color: ${ColorsWIP.Blue500};
  }
`;

const NoneInteractor: SVGViewportInteractor = {
  onMouseDown(viewport: SVGViewport, event: React.MouseEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
  },

  onWheel() {
    return;
  },

  render() {
    return <span />;
  },
};

export class SVGViewport extends React.Component<SVGViewportProps, SVGViewportState> {
  static Interactors = {
    PanAndZoom: PanAndZoomInteractor,
    None: NoneInteractor,
  };

  static defaultProps = {
    maxZoom: DEFAULT_ZOOM,
    maxAutocenterZoom: DEFAULT_MAX_AUTOCENTER_ZOOM,
  };

  element: React.RefObject<HTMLDivElement> = React.createRef();
  panzoom: any;

  _animation: any = null;
  _lastWheelTime = 0;
  _lastWheelDir = 0;

  state = {
    x: 0,
    y: 0,
    scale: DETAIL_ZOOM,
    minScale: 0,
  };

  componentDidMount() {
    this.autocenter();
  }

  cancelAnimations() {
    if (this._animation) {
      this._animation.cancel();
    }
  }

  autocenter(animate = false) {
    const el = this.element.current!;
    const ownerRect = {width: el.clientWidth, height: el.clientHeight};

    const dw = ownerRect.width / this.props.graphWidth;
    const dh = ownerRect.height / this.props.graphHeight;
    const desiredScale = Math.min(dw, dh);
    const boundedScale = Math.max(
      Math.min(desiredScale, this.props.maxAutocenterZoom),
      MIN_AUTOCENTER_ZOOM,
    );

    if (
      this.state.scale < boundedScale &&
      desiredScale !== boundedScale &&
      boundedScale === MIN_AUTOCENTER_ZOOM
    ) {
      // If the user is zoomed out past where they're going to land, AND where they're going to land
      // is not a view of the entire DAG but instead a view of some zoomed section, autocentering is
      // undesirable and should do nothing.
      return;
    }
    const target = {
      x: -(this.props.graphWidth / 2) * boundedScale + ownerRect.width / 2,
      y: -(this.props.graphHeight / 2) * boundedScale + ownerRect.height / 2,
      scale: boundedScale,
    };

    if (animate) {
      this.smoothZoom(target);
    } else {
      this.setState(Object.assign(target, {minScale: boundedScale}));
    }
  }

  screenToSVGCoords({x, y}: Point): Point {
    const el = this.element.current!;
    const {width, height} = el.getBoundingClientRect();
    return {
      x: (-(this.state.x - width / 2) + x - width / 2) / this.state.scale,
      y: (-(this.state.y - height / 2) + y - height / 2) / this.state.scale,
    };
  }

  getOffsetXY(e: MouseEvent | React.MouseEvent): Point | null {
    const el = this.element.current;
    if (!el) {
      return null;
    }
    const ownerRect = el.getBoundingClientRect();
    return {x: e.clientX - ownerRect.left, y: e.clientY - ownerRect.top};
  }

  public adjustZoomRelativeToScreenPoint(nextScale: number, point: Point) {
    const centerSVGCoord = this.screenToSVGCoords(point);
    const {scale} = this.state;
    let {x, y} = this.state;
    x = x + (centerSVGCoord.x * scale - centerSVGCoord.x * nextScale);
    y = y + (centerSVGCoord.y * scale - centerSVGCoord.y * nextScale);
    this.setState({x, y, scale: nextScale});
  }

  public smoothZoomToSVGCoords(x: number, y: number, scale: number) {
    const el = this.element.current!;
    const ownerRect = el.getBoundingClientRect();
    x = -x * scale + ownerRect.width / 2;
    y = -y * scale + ownerRect.height / 2;

    this.smoothZoom({x, y, scale});
  }

  public smoothZoom(to: {x: number; y: number; scale: number}) {
    const from = {scale: this.state.scale, x: this.state.x, y: this.state.y};

    if (this._animation) {
      this._animation.cancel();
    }

    this._animation = animate(from, to, {
      step: (v: any) => {
        this.setState({
          x: v.x,
          y: v.y,
          scale: v.scale,
        });
      },
      done: () => {
        this.setState(to);
        this._animation = null;
      },
    });
  }

  public getMaxZoom() {
    return this.props.maxZoom;
  }

  onZoomAndCenter = (event: React.MouseEvent<HTMLDivElement>) => {
    const offsetXY = this.getOffsetXY(event);
    if (!offsetXY) {
      return;
    }
    const offset = this.screenToSVGCoords(offsetXY);
    const maxZoom = this.props.maxZoom || DEFAULT_ZOOM;

    if (Math.abs(maxZoom - this.state.scale) < 0.01) {
      this.smoothZoomToSVGCoords(offset.x, offset.y, this.state.minScale);
    } else {
      this.smoothZoomToSVGCoords(offset.x, offset.y, maxZoom);
    }
  };

  onDoubleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    // Don't allow double-click events on the zoom slider to trigger this.
    if (event.target instanceof HTMLElement && event.target.closest('#zoom-slider-container')) {
      return;
    }
    this.props.onDoubleClick && this.props.onDoubleClick(event);
  };

  render() {
    const {children, onKeyDown, onClick, interactor, backgroundColor} = this.props;
    const {x, y, scale} = this.state;

    let viewport = {top: 0, left: 0, right: 0, bottom: 0};
    if (this.element.current) {
      const el = this.element.current!;
      const {width, height} = el.getBoundingClientRect();
      viewport = {
        left: -this.state.x / this.state.scale,
        top: -this.state.y / this.state.scale,
        right: (-this.state.x + width) / this.state.scale,
        bottom: (-this.state.y + height) / this.state.scale,
      };
    }

    return (
      <div
        ref={this.element}
        style={Object.assign({backgroundColor}, SVGViewportStyles)}
        onMouseDown={(e) => interactor.onMouseDown(this, e)}
        onWheel={(e) => interactor.onWheel(this, e)}
        onDoubleClick={this.onDoubleClick}
        onClick={onClick}
        onKeyDown={onKeyDown}
        tabIndex={-1}
      >
        <div
          style={{
            transformOrigin: `top left`,
            transform: `matrix(${scale}, 0, 0, ${scale}, ${x}, ${y})`,
          }}
        >
          {children(this.state, viewport)}
        </div>
        {interactor.render && interactor.render(this)}
      </div>
    );
  }
}

/*
BG: Not using styled-components here because I need a `ref` to an actual DOM element.
Styled-component with a ref returns a React component we need to findDOMNode to use.
*/
const SVGViewportStyles: React.CSSProperties = {
  width: '100%',
  height: '100%',
  position: 'relative',
  overflow: 'hidden',
  userSelect: 'none',
  outline: 'none',
};

const ZoomSliderContainer = styled.div`
  position: absolute;
  bottom: 0;
  right: 0;
  width: 30px;
  padding: 10px 8px;
  background: rgba(245, 248, 250, 0.4);
`;
