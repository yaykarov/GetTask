import React, { useState, useLayoutEffect, useEffect } from 'react';
import styles from './ScrollSlider.module.scss';
import InputSlider from 'react-input-slider';
import { ResizeSensor } from 'css-element-queries';

function useWindowSize() {
    const [size, setSize] = useState([0, 0]);
    useLayoutEffect(() => {
        function updateSize() {
            setSize([window.innerWidth, window.innerHeight]);
        }
        window.addEventListener('resize', updateSize);
        updateSize();
        return () => window.removeEventListener('resize', updateSize);
    }, []);
    return size;
}

function useElementSize(element) {
    const [size, setSize] = useState([0, 0]);
    useLayoutEffect(() => {
        if (element) {
            function updateSize() {
                setSize([element.clientWidth, window.clientHeight]);
            }
            const resize = new ResizeSensor(element, updateSize);
            updateSize();
            return () => resize.detach(updateSize);
        }
    }, [element]);
    return size;
}

function useElementScroll(element) {
    const [scroll, setScroll] = useState(0);
    useLayoutEffect(() => {
        if (element) {
            function updateScroll() {
                setScroll(element.scrollLeft);
            }
            element.addEventListener('scroll', updateScroll);
            updateScroll();
            return () => element.removeEventListener('scroll', updateScroll);
        }
    }, [element]);
    return scroll;
}

const ScrollSlider = ({ wrapRef, contentRef, children }) => {
    const [x, setX] = useState(0);
    const elScroll = useElementScroll(wrapRef.current);
    useWindowSize();
    useElementSize(contentRef.current);

    useEffect(() => setX(elScroll), [elScroll]);

    const getMax = () => {
        const wrapWidth = wrapRef.current ? wrapRef.current.clientWidth : 0;
        const contentWidth = contentRef.current ? contentRef.current.clientWidth : 0;
        let max = wrapWidth - contentWidth;
        if (x > -max) {
            setX(-max);
        }
        return max < 0 ? -max : max;
    };

    const sliderHandler = (x) => {
        wrapRef.current.scrollLeft = x;
    };

    return (
        <>
            <div className={styles.scrollWrapper}>
                <div className={styles.scrollContent}>
                    <div className={styles.forSlider} style={{}}>
                        <InputSlider
                            xmin={0}
                            xmax={getMax()}
                            className={styles.scroll}
                            styles={{
                                track: {
                                    backgroundColor: '#F2F2F2',
                                    height: '4px',
                                    borderRadius: '2px',
                                    display: 'block',
                                },
                                active: {
                                    backgroundColor: '#F2F2F2',
                                },
                                thumb: {
                                    width: '100px',
                                    height: '12px',
                                    // backgroundColor: '#D9D9D9',
                                    background:
                                        'linear-gradient(0deg, rgba(255,255,255,0) 0%, rgba(255,255,255,1) 32%, rgba(217,217,217,1) 33%, rgba(217,217,217,1) 66%, rgba(255,255,255,0) 67%, rgba(255,255,255,0) 100%)',
                                    borderRadius: '4px',
                                    boxShadow: 'none',
                                },
                            }}
                            axis='x'
                            x={elScroll}
                            onChange={({ x }) => sliderHandler(x)}
                        />
                    </div>
                    {children}
                </div>
            </div>
        </>
    );
};

export default ScrollSlider;
