import eventlet
eventlet.monkey_patch()

import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path('.') / '.env')
from flask import Flask, request, render_template, jsonify, redirect, url_for
from extensions import db
from models import Task, User
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.pool import NullPool
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', "varshitha_task_manager_secret_2024")
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "poolclass": NullPool
}

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ===== LOGIN CONFIG =====
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# ========================

def emit_analytics():
    tasks = Task.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    if not tasks:
        socketio.emit('analytics_update', {
            'total_tasks': 0,
            'completed_tasks': 0,
            'pending_tasks': 0,
            'completion_rate': 0,
            'priority_breakdown': {},
            'status_breakdown': {}
        })
        return
    
    task_list = [{'priority': t.priority, 'status': t.status} for t in tasks]
    df = pd.DataFrame(task_list)
    
    completed_tasks = len(df[df['status'] == 'Completed'])
    total_tasks = len(df)
    pending_tasks = total_tasks - completed_tasks
    completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    
    analytics_data = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'completion_rate': round(completion_rate, 2),
        'priority_breakdown': df['priority'].value_counts().to_dict(),
        'status_breakdown': df['status'].value_counts().to_dict()
    }
    socketio.emit('analytics_update', analytics_data)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit_analytics()

def broadcast_update():
    tasks = Task.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    tasks_list = [{
        'id': t.id,
        'title': t.title,
        'description': t.description,
        'status': t.status,
        'priority': t.priority
    } for t in tasks]
    
    socketio.emit('task_update', {'tasks': tasks_list})
    emit_analytics()

# ===== AUTH ROUTES =====
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return "Username already exists! <a href='/register'>Try again</a>"
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        return "Invalid username or password! <a href='/login'>Try again</a>"
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
# =======================

# ===== PROTECTED ROUTES =====
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    tasks_list = [{
        'id': t.id,
        'title': t.title,
        'description': t.description,
        'status': t.status,
        'priority': t.priority
    } for t in tasks]
    return jsonify(tasks_list)

@app.route('/api/tasks', methods=['POST'])
@login_required
def add_task():
    data = request.json
    new_task = Task(
        title=data['title'],
        description=data.get('description', ''),
        priority=data['priority'],
        status=data.get('status', 'Pending'),
        user_id=current_user.id
    )
    db.session.add(new_task)
    db.session.commit()
    broadcast_update()
    return jsonify({"message": "Task added"}), 201

@app.route('/api/tasks/<int:id>', methods=['PUT'])
@login_required
def update_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    data = request.json
    task.title = data.get('title', task.title)
    task.description = data.get('description', task.description)
    task.status = data.get('status', task.status)
    task.priority = data.get('priority', task.priority)
    db.session.commit()
    broadcast_update()
    return jsonify({"message": "Task updated"})

@app.route('/api/tasks/<int:id>', methods=['DELETE'])
@login_required
def delete_task(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    broadcast_update()
    return jsonify({"message": "Task deleted"})

@app.route('/api/analytics')
@login_required
def get_analytics():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    if not tasks:
        return jsonify({
            'total_tasks': 0,
            'completed_tasks': 0,
            'pending_tasks': 0,
            'completion_rate': 0,
            'priority_breakdown': {},
            'status_breakdown': {}
        })
    
    task_list = [{'priority': t.priority, 'status': t.status} for t in tasks]
    df = pd.DataFrame(task_list)
    
    completed_tasks = len(df[df['status'] == 'Completed'])
    total_tasks = len(df)
    pending_tasks = total_tasks - completed_tasks
    completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    
    analytics_data = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'completion_rate': round(completion_rate, 2),
        'priority_breakdown': df['priority'].value_counts().to_dict(),
        'status_breakdown': df['status'].value_counts().to_dict()
    }
    return jsonify(analytics_data)

with app.app_context():
    db.create_all()
    print(">>>Database Tables Created<<<")

if __name__ == '__main__':
    socketio.run(app, debug=True)
