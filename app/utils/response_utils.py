"""
Utilitário que facilita todos os retornos do sistema para
que seja padronizado, garantindo mais eficiencia no resultado
final e facilidade no tratamento posterior por app/site
"""

from flask import jsonify

def make_success_response(data, message, status_code=200):
    return jsonify({
        "status": "success",
        "data": data,
        "message": message
    }), status_code

def make_error_response(message, error_code, status_code):
    return jsonify({
        "status": "error",
        "data": None,
        "message": message,
        "error_code": error_code
    }), status_code