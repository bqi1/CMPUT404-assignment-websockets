#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect, jsonify
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        # self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        # self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space
    def replace_space(self,world):
        self.space = world
    def remove_listener(self,listener):
        try:
            self.listeners.remove(listener)
        except:
            return
    def get_listeners(self):
        return self.listeners
    

    

myWorld = World()        
myWorld.space["L"] = {"x":0,"y":2,"colour":"orange"}

# def set_listener( entity, data ):
#     ''' do something with the update ! '''

# myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect("/static/index.html", code = 301)

def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # XXX: TODO IMPLEMENT ME
    try:
        while True:
            message = ws.receive()
            if (message is not None): # IF message exists:
                recv_coordinate = json.loads(message)  # Load the coordinates. Should be structured as {entity_name:entity_data}    
                for key in recv_coordinate.keys():
                    if recv_coordinate[key] == {}: # If an empty entity, send entire world
                        ws.send(json.dumps(myWorld.world()))
                    elif (key in myWorld.world().keys()): # If entity exists, update it, then send update to all
                        myWorld.set(key,recv_coordinate[key])
                        send_all(json.dumps({key:myWorld.get(key)}))
                    elif not (key in myWorld.world().keys()): # If entity does not exist, create and send update to others
                        myWorld.set(key,recv_coordinate[key])
                        send_others(client,json.dumps({key:myWorld.get(key)}))
            else:
                break
    except Exception as e:
        print("closed")
        print(e)
# Code taken from Abram Hindle at 2021-03-24 at https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py
class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()
def send_all(msg): # Send via the websocket to all clients
    for client in myWorld.get_listeners():
        client.put( msg )
############################################################
def send_others(client,msg): # Send to all clients except the current client via websocket
    for other_client in myWorld.get_listeners():
        if not (client == other_client):
            other_client.put(msg)

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    # XXX: TODO IMPLEMENT ME'
    client = Client()
    myWorld.add_set_listener(client)
    g = gevent.spawn(read_ws,ws,client)
    try:
        while True:
            msg = client.get()
            ws.send(msg)
    except Exception as e:
        print(e)
    finally:
        myWorld.remove_listener(client)
        gevent.kill(g)

# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])


# Code taken from Assignment 4
@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    data = flask_post_json()
    if type(data) is dict and 'x' in data and 'y' in data:
        myWorld.set(entity,data)
        response = jsonify(data)
        response.status_code = 200
    else:
        response = jsonify(success = False)
        response.status_code = 400
    return response

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    if flask.request.method == 'POST':
        potential_world_dict = flask_post_json()
        if type(potential_world_dict) is dict:
            myWorld.replace_space(potential_world_dict)
    response = jsonify(myWorld.world())
    response.status_code = 200
    return response

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    try:
        response = jsonify(myWorld.get(entity))
        response.status_code = 200
    except KeyError:
        response = jsonify(found = False)
        response.status_code = 200
    return response
@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    response = jsonify(myWorld.world())
    response.status_code = 200
    return response
if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
