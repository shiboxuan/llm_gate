/**
 * Register page - split layout with animated brand panel and registration form.
 */
import React, {useState, useEffect} from 'react';
import {Form, Input, Button, message} from 'antd';
import {Icon} from '@iconify/react';
import {LockOutlined, UserOutlined, MailOutlined} from '@ant-design/icons';
import {useNavigate, useSearchParams, Link} from 'react-router-dom';
import {register, setToken, getToken} from '@/api';
import './index.less';

const Register: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [loading, setLoading] = useState(false);

    // If already logged in, redirect to home
    useEffect(() => {
        if (getToken()) {
            navigate('/', {replace: true});
        }
    }, [navigate]);

    const handleSubmit = async (values: {username: string; password: string; email?: string}) => {
        setLoading(true);
        try {
            const response = await register({
                username: values.username,
                password: values.password,
                email: values.email || undefined
            });
            setToken(response.data.access_token);
            message.success('注册成功');
            const returnUrl = searchParams.get('returnUrl') || '/';
            navigate(returnUrl, {replace: true});
        } catch (error: any) {
            const msg = error.response?.data?.detail || error.response?.data?.message || '注册失败，请稍后重试';
            message.error(typeof msg === 'string' ? msg : '注册失败，请稍后重试');
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
                    <h1 className='brand-title'>开启你的 AI 网关之旅</h1>
                    <p className='brand-subtitle'>
                        注册账号，即可集中管理多个 AI 模型的 API 调用，为你的工具提供统一入口。
                    </p>
                    <div className='brand-features'>
                        <div className='feature-item'>
                            <Icon icon='heroicons:check-circle' />
                            <span>免费注册，即开即用</span>
                        </div>
                        <div className='feature-item'>
                            <Icon icon='heroicons:check-circle' />
                            <span>支持 OpenAI / Anthropic / Azure</span>
                        </div>
                        <div className='feature-item'>
                            <Icon icon='heroicons:check-circle' />
                            <span>API Key 加密存储，安全可靠</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Right form panel */}
            <div className='auth-form-panel'>
                <div className='auth-form-wrapper'>
                    <div className='auth-form-header'>
                        <h2>创建账号</h2>
                        <p>填写以下信息完成注册</p>
                    </div>

                    <Form layout='vertical' onFinish={handleSubmit} autoComplete='off' size='large'>
                        <Form.Item
                            name='username'
                            label='用户名'
                            rules={[
                                {required: true, message: '请输入用户名'},
                                {min: 3, message: '用户名至少 3 个字符'},
                                {max: 32, message: '用户名最多 32 个字符'},
                                {pattern: /^[a-zA-Z0-9_-]+$/, message: '用户名只能包含字母、数字、下划线和连字符'}
                            ]}
                        >
                            <Input prefix={<UserOutlined />} placeholder='请输入用户名' />
                        </Form.Item>
                        <Form.Item
                            name='email'
                            label='邮箱（选填）'
                            rules={[{type: 'email', message: '请输入有效的邮箱地址'}]}
                        >
                            <Input prefix={<MailOutlined />} placeholder='your@email.com' />
                        </Form.Item>
                        <Form.Item
                            name='password'
                            label='密码'
                            rules={[
                                {required: true, message: '请输入密码'},
                                {min: 6, message: '密码至少 6 个字符'}
                            ]}
                        >
                            <Input.Password prefix={<LockOutlined />} placeholder='请输入密码' />
                        </Form.Item>
                        <Form.Item
                            name='confirmPassword'
                            label='确认密码'
                            dependencies={['password']}
                            rules={[
                                {required: true, message: '请确认密码'},
                                ({getFieldValue}) => ({
                                    validator(_, value) {
                                        if (!value || getFieldValue('password') === value) {
                                            return Promise.resolve();
                                        }
                                        return Promise.reject(new Error('两次输入的密码不一致'));
                                    }
                                })
                            ]}
                        >
                            <Input.Password prefix={<LockOutlined />} placeholder='请再次输入密码' />
                        </Form.Item>
                        <Form.Item style={{marginBottom: 16}}>
                            <Button type='primary' htmlType='submit' loading={loading} block className='auth-submit-btn'>
                                注册
                            </Button>
                        </Form.Item>
                    </Form>

                    <div className='auth-switch'>
                        已有账号？<Link to='/login'>去登录</Link>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Register;
