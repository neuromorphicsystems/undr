import * as React from "react";
import * as utilities from "./utilities";

export interface Dimensions {
    width: number | null;
    height: number | null;
}

export default function useDimensions<Element extends HTMLElement>(): [
    React.RefObject<Element>,
    Dimensions
] {
    const element = React.useRef<Element>(null);
    const [dimensions, setDimensions] = React.useState<Dimensions>({
        width: null,
        height: null,
    });
    React.useEffect(() => {
        if (element.current != null) {
            setDimensions({
                width: element.current.offsetWidth,
                height: element.current.offsetHeight,
            });
        }
        if (element.current == null) {
            throw new Error("unassigned element reference");
        }
        const listener = utilities.debounce(event => {
            setDimensions({
                width: (event as unknown as ResizeObserverSize).inlineSize,
                height: (event as unknown as ResizeObserverSize).blockSize,
            });
        }, 16);
        const observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                listener.handleEvent(
                    entry.borderBoxSize[0] as unknown as Event
                );
            }
        });
        observer.observe(element.current);
        return function cleanup() {
            observer.disconnect();
            listener.reset();
        };
    }, []);
    return [element, dimensions];
}
