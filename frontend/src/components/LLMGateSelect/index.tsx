/**
 * LLM Gate 专属 Select 下拉框组件
 * 选中项使用浅紫色背景，与 LLM Gate 主题风格一致
 */
import React from 'react';
import {Select, SelectProps} from 'antd';
import './index.less';

// 组件专属的下拉面板类名
const POPUP_CLASS_NAME = 'llm-gate-select-dropdown';

export interface LLMGateSelectProps extends SelectProps {
    // 可以在这里扩展专属属性
}

const LLMGateSelect: React.FC<LLMGateSelectProps> = ({
    popupClassName,
    className,
    ...restProps
}) => {
    // 合并自定义 popupClassName
    const mergedPopupClassName = popupClassName
        ? `${POPUP_CLASS_NAME} ${popupClassName}`
        : POPUP_CLASS_NAME;

    // 合并自定义 className
    const mergedClassName = className
        ? `llm-gate-select ${className}`
        : 'llm-gate-select';

    return (
        <Select
            {...restProps}
            className={mergedClassName}
            popupClassName={mergedPopupClassName}
        />
    );
};

export default LLMGateSelect;
