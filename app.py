import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path('.') / '.env')
from flask import Flask, request, render_template, jsonify
from extensions import db
from models import Task
from flask_socketio import SocketIO, emit
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "varshitha_task_manager_secret_2024"
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

def emit_analytics():
    tasks = Task.query.all()
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
    tasks = Task.query.all()
    tasks_list = [{
        'id': t.id,
        'title': t.title,
        'description': t.description,
        'status': t.status,
        'priority': t.priority
    } for t in tasks]
    
    socketio.emit('task_update', {'tasks': tasks_list})
    emit_analytics()

# ===== API ROUTES =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tasks = Task.query.all()
    tasks_list = [{
        'id': t.id,
        'title': t.title,
        'description': t.description,
        'status': t.status,
        'priority': t.priority
    } for t in tasks]
    return jsonify(tasks_list)

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.json
    new_task = Task(
        title=data['title'],
        description=data.get('description', ''),
        priority=data['priority'],
        status=data.get('status', 'Pending')
    )
    db.session.add(new_task)
    db.session.commit()
    broadcast_update()
    return jsonify({"message": "Task added"}), 201

@app.route('/api/tasks/<int:id>', methods=['PUT'])
def update_task(id):
    task = Task.query.get_or_404(id)
    data = request.json
    task.title = data.get('title', task.title)
    task.description = data.get('description', task.description)
    task.status = data.get('status', task.status)
    task.priority = data.get('priority', task.priority)
    db.session.commit()
    broadcast_update()
    return jsonify({"message": "Task updated"})

@app.route('/api/tasks/<int:id>', methods=['DELETE'])
def delete_task(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    broadcast_update()
    return jsonify({"message": "Task deleted"})

@app.route('/api/analytics')
def get_analytics():
    tasks = Task.query.all()
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
