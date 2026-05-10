import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path('.') / '.env')
from flask import Flask, request, render_template,jsonify
from extensions import db
from models import Task
from flask_socketio import SocketIO, emit  
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']="postgresql://taskdb_a743_user:LZ4nSdyWtwReQTRL2D2Tra3dXrCWh0U8@dpg-d802a5mgvqtc73d48rd0-a/taskdb_a743?sslmode=require"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] ="varshitha_task_manager_secret_2024"
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*") 
 with app.app_context():
 db.create_all()
print(">>> Database Tables Created <<<")
def emit_analytics():
    tasks = Task.query.all()
    if not tasks:
        socketio.emit('analytics_update', {'total_tasks': 0, 'completion_rate': 0, 'priority_breakdown': {}, 'status_breakdown': {}})
        return
    
    task_list = [{'priority': t.priority, 'status': t.status} for t in tasks]
    df = pd.DataFrame(task_list)
    total_tasks = len(df)
    completed_tasks = len(df[df['status'] == 'Completed'])
    completion_rate = np.round((completed_tasks / total_tasks) * 100, 2)
    priority_counts = df['priority'].value_counts().to_dict()
    status_counts = df['status'].value_counts().to_dict()
    
    socketio.emit('analytics_update', {
        'total_tasks': int(total_tasks),
        'completion_rate': float(completion_rate),
        'priority_breakdown': priority_counts,
        'status_breakdown': status_counts
    })
@app.route('/')
def home():
    return render_template('index.html')
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tasks = Task.query.all()
    return jsonify([task.to_dict() for task in tasks])

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    new_task = Task(
        title=data['title'],
        description=data.get('description', ''),
        priority=data.get('priority', 'Medium'),
        status=data.get('status', 'Pending')
    )
    db.session.add(new_task)
    db.session.commit()
    emit_analytics()
    return jsonify({"message": "Task Added Successfully", "task": new_task.to_dict()}), 201
@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Task not found'}), 404
    data = request.get_json()
    task.title = data.get('title', task.title)
    task.description = data.get('description', task.description)
    task.priority = data.get('priority', task.priority)
    task.status = data.get('status', task.status)
    db.session.commit()
    emit_analytics()
    return jsonify({'message': 'Task Updated Successfully', 'task': {
        'id': task.id, 'title': task.title, 'description': task.description,
        'priority': task.priority, 'status': task.status
    }}), 200

# STEP 13.2: DELETE TASK - DELETE /api/tasks/<id>
@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Task not found'}), 404
    db.session.delete(task)
    db.session.commit()
    emit_analytics()
    return jsonify({'message': 'Task Deleted Successfully'}), 200

# STEP 13.3: GET SINGLE TASK - GET /api/tasks/<id>
@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Task not found'}), 404
    return jsonify({
        'id': task.id, 'title': task.title, 'description': task.description,
        'priority': task.priority, 'status': task.status
    }), 200
@app.route('/api/analytics')
def get_analytics():
    # 1. Database nunchi anni tasks teesko
    tasks = Task.query.all()
    
    # 2. Tasks empty ga unte message pampu
    if not tasks:
        return jsonify({
            'total_tasks': 0,
            'completion_rate': 0,
            'priority_breakdown': {},
            'status_breakdown': {}
        })
    
    # 3. Pandas DataFrame loki marchu
    task_list = []
    for task in tasks:
        task_list.append({
            'id': task.id,
            'title': task.title,
            'priority': task.priority,
            'status': task.status,
            'created_at': task.created_at
        })
    
    df = pd.DataFrame(task_list)
    
    # 4. NUMPY THO COMPLETION RATE LEKKAPETTU
    total_tasks = len(df)
    completed_tasks = len(df[df['status'] == 'Completed'])
    completion_rate = np.round((completed_tasks / total_tasks) * 100, 2)
    
    # 5. PANDAS THO COUNTS TEESKO
    priority_counts = df['priority'].value_counts().to_dict()
    status_counts = df['status'].value_counts().to_dict()
    
    # 6. JSON response pampu
    return jsonify({
        'total_tasks': int(total_tasks),
        'completion_rate': float(completion_rate),
        'priority_breakdown': priority_counts,
        'status_breakdown': status_counts
    })
if __name__ == '__main__':
     socketio.run(app, debug=True) 
