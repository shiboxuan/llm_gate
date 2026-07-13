/**
 * Login page - split layout with animated brand panel and login form.
 */
import React, {useState, useEffect} from 'react';
import {Form, Input, Button, message} from 'antd';
import {Icon} from '@iconify/react';
import {LockOutlined, UserOutlined} from '@ant-design/icons';
import {useNavigate, useSearchParams, Link} from 'react-router-dom';
import {login, setToken, getToken} from '@/api';
import './index.less';

const Login: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [loading, setLoading] = useState(false);

    // If already logged in, redirect to home
    useEffect(() => {
        if (getToken()) {
            navigate('/', {replace: true});
        }
    }, [navigate]);

    const handleSubmit = async (values: {username: string; password: string}) => {
        setLoading(true);
        try {
            const response = await login(values);
            setToken(response.data.access_token);
            message.success('登录成功');
            const returnUrl = searchParams.get('returnUrl') || '/';
            navigate(returnUrl, {replace: true});
        } catch (error: any) {
            const msg = error.response?.data?.detail || error.response?.data?.message || '登录失败，请检查用户名和密码';
            message.error(typeof msg === 'string' ? msg : '登录失败，请检查用户名和密码');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className='auth-page'>
            {/* Left brand panel */}
            <div className='auth-brand-panel'>
                <div className='brand-shapes'>
                    <span className='shape shape-1'></span>
                    <span className='shape shape-2'></span>
                    <span className='shape shape-3'></span>
                    <span className='shape shape-4'></span>
                    <span className='shape shape-5'></span>
                </div>
                <div className='brand-content'>
                    <div className='brand-logo'>
                        <Icon icon='heroicons:bolt-20-solid' />
                        <span>LLM Gate</span>
                    </div>
                    <h1 className='brand-title'>统一 LLM 网关</h1>
                    <p className='brand-subtitle'>
                        集中管理多个 AI 模型的 API 调用，为 Cline、Cursor 等工具提供统一的 API 入口。
                    </p>
                    <div className='brand-features'>
                        <div className='feature-item'>
                            <Icon icon='heroicons:check-circle' />
                            <span>多模型统一路由</span>
                        </div>
                        <div className='feature-item'>
                            <Icon icon='heroicons:check-circle' />
                            <span>密钥安全加密存储</span>
                        </div>
                        <div className='feature-item'>
                            <Icon icon='heroicons:check-circle' />
                            <span>Token 用量实时统计</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Right form panel */}
            <div className='auth-form-panel'>
                <div className='auth-form-wrapper'>
                    <div className='auth-form-header'>
                        <h2>欢迎回来</h2>
                        <p>请登录您的账号</p>
                    </div>

                    <Form layout='vertical' onFinish={handleSubmit} autoComplete='off' size='large'>
                        <Form.Item name='username' label='用户名' rules={[{required: true, message: '请输入用户名'}]}>
                            <Input prefix={<UserOutlined />} placeholder='请输入用户名' />
                        </Form.Item>
                        <Form.Item name='password' label='密码' rules={[{required: true, message: '请输入密码'}]}>
                            <Input.Password prefix={<LockOutlined />} placeholder='请输入密码' />
                        </Form.Item>
                        <Form.Item style={{marginBottom: 16}}>
                            <Button type='primary' htmlType='submit' loading={loading} block className='auth-submit-btn'>
                                登录
                            </Button>
                        </Form.Item>
                    </Form>

                    <div className='auth-switch'>
                        还没有账号？<Link to='/register'>立即注册</Link>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Login;
