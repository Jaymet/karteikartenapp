from flask import Flask, render_template, request, redirect, url_for, session, flash
# import data_manager # Importiere unseren data_manager -> Entfernt, da nicht benötigt
import os # für secret_key und Dateiprüfung
import random # For shuffling choices and selecting questions

app = Flask(__name__)
app.secret_key = os.urandom(24) # Needed for session management

@app.route('/')
def index():
    data = data_manager.load_data()
    lernsets = data.get("lernsets", [])
    return render_template('index.html', lernsets=lernsets)

@app.route('/create_set', methods=['GET', 'POST'])
def create_lernset():
    if request.method == 'POST':
        titel = request.form.get('titel')
        beschreibung = request.form.get('beschreibung')

        if not titel:
            flash("Titel ist erforderlich!", "danger")
            return render_template('create_set.html'), 400 # Render again with form data

        data = data_manager.load_data()

        new_set = {
            "id": data_manager.generate_uuid(),
            "titel": titel,
            "beschreibung": beschreibung,
            "karten": [] # Ein neues Set hat anfangs keine Karten
        }

        data["lernsets"].append(new_set)
        data_manager.save_data(data)
        flash(f"Lernset '{titel}' erfolgreich erstellt!", "success")
        return redirect(url_for('index'))

    return render_template('create_set.html')

@app.route('/set/<set_id>')
def view_lernset(set_id):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)
    if lernset:
        stats = calculate_set_statistics(lernset)
        return render_template('view_set.html', lernset=lernset, stats=stats)
    flash("Lernset nicht gefunden.", "danger")
    return redirect(url_for('index'))

@app.route('/set/<set_id>/add_card', methods=['POST'])
def add_card(set_id):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))

    begriff = request.form.get('begriff')
    definition = request.form.get('definition')

    if not begriff or not definition:
        flash("Begriff und Definition sind für eine neue Karte erforderlich!", "danger")
        return redirect(url_for('view_lernset', set_id=set_id))

    new_card = {
        "id": data_manager.generate_uuid(),
        "begriff": begriff,
        "definition": definition,
        "lernfortschritt": 0
    }

    lernset['karten'].append(new_card)
    data_manager.save_data(data)
    flash("Neue Karte erfolgreich zum Set hinzugefügt!", "success")
    return redirect(url_for('view_lernset', set_id=set_id))

@app.route('/set/<set_id>/learn/<int:card_index>')
def learn_card(set_id, card_index):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))

    if not lernset['karten']:
        flash("Dieses Lernset enthält noch keine Karten.", "info")
        return redirect(url_for('view_lernset', set_id=set_id))

    total_cards = len(lernset['karten'])

    if not (0 <= card_index < total_cards):
        # Index außerhalb des gültigen Bereichs, vielleicht zur ersten Karte leiten oder Fehler
        # Fürs Erste leiten wir zur ersten Karte.
        if total_cards > 0:
            return redirect(url_for('learn_card', set_id=set_id, card_index=0))
        else: # Sollte durch die Prüfung oben abgedeckt sein, aber sicher ist sicher
             return redirect(url_for('view_lernset', set_id=set_id))


    current_karte = lernset['karten'][card_index]

    prev_card_index = card_index - 1 if card_index > 0 else None
    next_card_index = card_index + 1 if card_index < total_cards - 1 else None

    return render_template('learn_card.html',
                           lernset=lernset,
                           karte=current_karte,
                           card_index=card_index,
                           prev_card_index=prev_card_index,
                           next_card_index=next_card_index,
                           current_card_number=card_index + 1,
                           total_cards=total_cards)

@app.route('/set/<set_id>/study/<int:card_index>', methods=['GET'])
def study_mode_card(set_id, card_index):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))
    if not lernset['karten']:
        flash("Dieses Lernset enthält noch keine Karten.", "info")
        return redirect(url_for('view_lernset', set_id=set_id))

    total_cards = len(lernset['karten'])
    if not (0 <= card_index < total_cards):
        flash("Ungültiger Kartenindex.", "warning")
        if total_cards > 0: return redirect(url_for('study_mode_card', set_id=set_id, card_index=0))
        else: return redirect(url_for('view_lernset', set_id=set_id)) # Sollte durch obige Prüfung abgedeckt sein

    current_karte = lernset['karten'][card_index]
    prev_card_index = card_index - 1 if card_index > 0 else None
    next_card_index = card_index + 1 if card_index < total_cards - 1 else None

    # Feedback-Parameter aus der Session holen, falls vorhanden (nach einer Antwort-Prüfung)
    feedback_params = request.args.get('feedback_params', None)
    feedback_data = {}
    if feedback_params:
        # In einem realen Szenario würde man das sicherer handhaben oder über die Session/Flash-Nachrichten
        # Hier parsen wir es einfach aus den query-Parametern
        # Beispiel: "correct=True&feedback_text=Richtig!"
        try:
            params = dict(qc.split("=") for qc in feedback_params.split("&"))
            feedback_data['feedback'] = True # Signalisiert, dass Feedback da ist
            feedback_data['correct'] = params.get('correct', 'False').lower() == 'true'
            feedback_data['feedback_text'] = params.get('feedback_text', 'Kein Feedback Text.')
            # Wenn falsch, muss die korrekte Definition erneut geladen/übergeben werden
            # Das ist bereits in current_karte.definition enthalten.
        except ValueError: # Falls das Parsen fehlschlägt
            feedback_data['feedback'] = False


    return render_template('study_card.html',
                           lernset=lernset,
                           karte=current_karte,
                           card_index=card_index,
                           prev_card_index=prev_card_index,
                           next_card_index=next_card_index,
                           current_card_number=card_index + 1,
                           total_cards=total_cards,
                           **feedback_data)


@app.route('/set/<set_id>/study/<int:card_index>/check', methods=['POST'])
def check_answer(set_id, card_index):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))
    if not (0 <= card_index < len(lernset['karten'])):
        flash("Ungültiger Kartenindex für Antwortüberprüfung.", "danger")
        return redirect(url_for('view_lernset', set_id=set_id))

    karte = lernset['karten'][card_index]
    user_definition = request.form.get('user_definition', '').strip()

    # Einfache Überprüfung (Groß-/Kleinschreibung ignorieren, Leerzeichen am Rand entfernen)
    is_correct = user_definition.lower() == karte['definition'].strip().lower()

    feedback_text = "Richtig!" if is_correct else "Leider falsch."

    if is_correct:
        # Optional: Lernfortschritt erhöhen
        karte['lernfortschritt'] = karte.get('lernfortschritt', 0) + 1
        data_manager.save_data(data) # Fortschritt speichern
    else:
        # Optional: Lernfortschritt verringern oder als "noch zu lernen" markieren
        karte['lernfortschritt'] = max(0, karte.get('lernfortschritt', 0) - 1) # Nicht unter 0 gehen lassen
        data_manager.save_data(data)


    # Parameter für das Feedback zusammenstellen, um sie an die GET-Route zu übergeben
    # Dies ist eine einfache Methode. Flash-Nachrichten wären hier eleganter.
    feedback_params = f"correct={is_correct}&feedback_text={feedback_text}"

    # Umleiten zur study_mode_card Ansicht derselben Karte, aber mit Feedback
    # Die Feedback-Parameter werden als Query-Argumente übergeben
    return redirect(url_for('study_mode_card',
                            set_id=set_id,
                            card_index=card_index,
                            feedback_params=feedback_params))

@app.route('/set/<set_id>/write/<int:card_index>', methods=['GET'])
def write_mode_card(set_id, card_index):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))
    if not lernset['karten']:
        flash("Dieses Lernset enthält noch keine Karten.", "info")
        return redirect(url_for('view_lernset', set_id=set_id))

    total_cards = len(lernset['karten'])
    if not (0 <= card_index < total_cards):
        flash("Ungültiger Kartenindex.", "warning")
        if total_cards > 0: return redirect(url_for('write_mode_card', set_id=set_id, card_index=0))
        else: return redirect(url_for('view_lernset', set_id=set_id))

    current_karte = lernset['karten'][card_index]
    prev_card_index = card_index - 1 if card_index > 0 else None
    next_card_index = card_index + 1 if card_index < total_cards - 1 else None

    feedback_params = request.args.get('feedback_params', None)
    feedback_data = {}
    if feedback_params:
        try:
            params = dict(qc.split("=") for qc in feedback_params.split("&"))
            feedback_data['feedback'] = True
            feedback_data['correct'] = params.get('correct', 'False').lower() == 'true'
            feedback_data['feedback_text'] = params.get('feedback_text', 'Kein Feedback Text.')
        except ValueError:
            feedback_data['feedback'] = False

    return render_template('write_mode.html',
                           lernset=lernset,
                           karte=current_karte,
                           card_index=card_index,
                           prev_card_index=prev_card_index,
                           next_card_index=next_card_index,
                           current_card_number=card_index + 1,
                           total_cards=total_cards,
                           **feedback_data)

@app.route('/set/<set_id>/write/<int:card_index>/check', methods=['POST'])
def check_written_term(set_id, card_index):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))
    if not (0 <= card_index < len(lernset['karten'])):
        flash("Ungültiger Kartenindex für Antwortüberprüfung.", "danger")
        return redirect(url_for('view_lernset', set_id=set_id))

    karte = lernset['karten'][card_index]
    user_term = request.form.get('user_term', '').strip()

    is_correct = user_term.lower() == karte['begriff'].strip().lower()

    feedback_text = "Richtig!" if is_correct else "Leider falsch."

    # Update lernfortschritt (optional, aber konsistent mit study_mode)
    if is_correct:
        karte['lernfortschritt'] = karte.get('lernfortschritt', 0) + 1
    else:
        karte['lernfortschritt'] = max(0, karte.get('lernfortschritt', 0) - 1)
    data_manager.save_data(data)

    feedback_params = f"correct={is_correct}&feedback_text={feedback_text}"

    return redirect(url_for('write_mode_card',
                            set_id=set_id,
                            card_index=card_index,
                            feedback_params=feedback_params))

# --------------- Test Modus Helfer und Routen ---------------

def generate_multiple_choice_questions(lernset, num_questions=None, num_options=4):
    """
    Generiert Multiple-Choice-Fragen für ein Lernset.
    Fragetyp: Begriff gegeben, Definition auswählen.
    """
    karten = lernset.get('karten', [])
    if not karten:
        return []

    if num_questions is None or num_questions > len(karten):
        questions_to_generate = karten[:] # Alle Karten nehmen
    else:
        questions_to_generate = random.sample(karten, num_questions)

    generated_test_questions = []

    for karte in questions_to_generate:
        correct_answer = karte['definition']

        # Optionen sammeln (alle Definitionen außer der korrekten)
        options = [k['definition'] for k in karten if k['id'] != karte['id']]

        # Wenn nicht genügend einzigartige Optionen vorhanden sind, fülle mit generischen oder wiederhole (nicht ideal)
        # Fürs Erste: Wenn weniger als num_options-1 falsche Optionen da sind, reduziere num_options für diese Frage
        actual_num_options = num_options
        if len(options) < num_options - 1:
            # Nicht genug Distraktoren. Man könnte hier noch Dummy-Antworten einfügen
            # oder die Anzahl der Optionen für diese Frage reduzieren.
            # Fürs Erste nehmen wir alle verfügbaren Distraktoren.
            distractors = options[:]
        else:
            distractors = random.sample(options, min(len(options), num_options - 1))

        all_choices = [correct_answer] + distractors
        random.shuffle(all_choices)

        question_data = {
            'id': karte['id'], # ID der Originalkarte
            'term': karte['begriff'],
            'options': all_choices,
            'correct_answer_definition': correct_answer, # Zur späteren Überprüfung
            'user_answer': None, # Wird später gefüllt
            'is_correct': None # Wird später gefüllt
        }
        generated_test_questions.append(question_data)

    return generated_test_questions


@app.route('/set/<set_id>/start_test')
def start_test(set_id):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))

    # Mindestanzahl von Karten, damit der Test-Modus überhaupt Sinn macht.
    # generate_multiple_choice_questions kommt mit < num_options Karten zurecht, aber < 1 ist nicht sinnvoll.
    if not lernset.get('karten') or len(lernset['karten']) < 1:
        flash(f"Dieses Lernset hat nicht genügend Karten für einen Test (mind. 1 Karte benötigt).", "warning")
        return redirect(url_for('view_lernset', set_id=set_id))

    # Generiere Testfragen (z.B. alle Karten des Sets, max 4 Optionen)
    # Die Funktion generate_multiple_choice_questions ist dafür verantwortlich,
    # auch mit wenigen Karten (weniger als num_options) umzugehen.
    test_questions = generate_multiple_choice_questions(lernset, num_options=4)

    if not test_questions: # Sollte nur passieren, wenn lernset['karten'] leer war, was oben abgefangen wird. Doppelt sicher.
        flash("Konnte keine Testfragen generieren, da das Set leer ist oder ein unerwarteter Fehler aufgetreten ist.", "danger")
        return redirect(url_for('view_lernset', set_id=set_id))

    session['current_test'] = {
        'set_id': set_id,
        'set_title': lernset['titel'],
        'questions': test_questions,
        'current_question_index': 0,
        'score': 0
    }
    return redirect(url_for('test_question_view', set_id=set_id, q_index=0))


@app.route('/set/<set_id>/test/question/<int:q_index>')
def test_question_view(set_id, q_index):
    if 'current_test' not in session or session['current_test']['set_id'] != set_id:
        flash("Kein aktiver Test gefunden oder Test für ein anderes Set. Starte einen neuen Test.", "info")
        return redirect(url_for('start_test', set_id=set_id))

    test_data = session['current_test']

    if not (0 <= q_index < len(test_data['questions'])):
        if q_index >= len(test_data['questions']) and len(test_data['questions']) > 0: # Test beendet
             return redirect(url_for('test_results', set_id=set_id))
        flash("Ungültiger Fragenindex im Test.", "danger")
        # Sicherstellen, dass der User nicht in einer Schleife landet, wenn test_data['questions'] leer ist
        if not test_data['questions']:
            flash("Test enthält keine Fragen.", "warning")
            return redirect(url_for('view_lernset', set_id=set_id))
        return redirect(url_for('test_question_view', set_id=set_id, q_index=0))


    current_question_data = test_data['questions'][q_index]

    # Stelle sicher, dass der Index in der Session aktuell ist
    session['current_test']['current_question_index'] = q_index
    session.modified = True


    return render_template('test_question.html',
                           test_data=test_data,
                           question=current_question_data)

@app.route('/set/<set_id>/test/question/<int:q_index>/submit', methods=['POST'])
def submit_test_answer(set_id, q_index):
    if 'current_test' not in session or session['current_test']['set_id'] != set_id:
        flash("Kein aktiver Test gefunden oder Test für ein anderes Set. Starte einen neuen Test.", "info")
        return redirect(url_for('start_test', set_id=set_id))

    test_data = session['current_test']

    if not (0 <= q_index < len(test_data['questions'])):
        flash("Ungültiger Fragenindex bei der Antwortabgabe.", "danger")
        return redirect(url_for('test_results', set_id=set_id)) # Gehe zu den Ergebnissen, wenn Index falsch ist

    user_answer = request.form.get('answer')
    if user_answer is None:
        flash("Bitte wähle eine Antwort aus.", "warning")
        return redirect(url_for('test_question_view', set_id=set_id, q_index=q_index))

    correct_answer = test_data['questions'][q_index]['correct_answer_definition']

    is_correct = (user_answer == correct_answer)

    test_data['questions'][q_index]['user_answer'] = user_answer
    test_data['questions'][q_index]['is_correct'] = is_correct

    if is_correct:
        test_data['score'] += 1

    session['current_test'] = test_data # Update session
    session.modified = True

    next_q_index = q_index + 1
    if next_q_index < len(test_data['questions']):
        return redirect(url_for('test_question_view', set_id=set_id, q_index=next_q_index))
    else:
        # Test finished
        return redirect(url_for('test_results', set_id=set_id))

@app.route('/set/<set_id>/test/results')
def test_results(set_id):
    if 'current_test' not in session or session['current_test']['set_id'] != set_id:
        flash("Keine Testergebnisse zum Anzeigen gefunden oder Test für ein anderes Set.", "info")
        return redirect(url_for('view_lernset', set_id=set_id))

    test_data = session['current_test']

    # Optional: Clear test data from session after viewing results once,
    # or keep it to allow revisiting. For now, keep it.
    # To clear: session.pop('current_test', None)

    return render_template('test_results.html', test_data=test_data)

# --------------- Statistik Helfer ---------------

def calculate_set_statistics(lernset):
    if not lernset or not lernset.get('karten'):
        return {
            "total_cards": 0,
            "cards_learned": 0, # Beispiel: lernfortschritt > 1 als "gelernt"
            "cards_in_progress": 0, # Beispiel: lernfortschritt == 1 als "in Arbeit"
            "cards_new": 0, # Beispiel: lernfortschritt == 0 als "neu"
            "percentage_learned": 0
        }

    karten = lernset['karten']
    total_cards = len(karten)

    # Annahme: lernfortschritt = 0 (neu), 1 (in Arbeit/einmal richtig), >1 (gut gelernt/mehrmals richtig)
    cards_learned = sum(1 for k in karten if k.get('lernfortschritt', 0) > 1)
    cards_in_progress = sum(1 for k in karten if k.get('lernfortschritt', 0) == 1)
    cards_new = sum(1 for k in karten if k.get('lernfortschritt', 0) == 0)

    percentage_learned = (cards_learned / total_cards * 100) if total_cards > 0 else 0

    return {
        "total_cards": total_cards,
        "cards_learned": cards_learned,
        "cards_in_progress": cards_in_progress,
        "cards_new": cards_new,
        "percentage_learned": round(percentage_learned, 1)
    }

# --------------- Matching Game Routen ---------------

@app.route('/set/<set_id>/matching_game')
def matching_game_start(set_id):
    data = data_manager.load_data()
    lernset = next((s for s in data['lernsets'] if s['id'] == set_id), None)

    if not lernset:
        flash("Lernset nicht gefunden.", "danger")
        return redirect(url_for('index'))

    karten = lernset.get('karten', [])
    min_cards_for_game = 2
    if len(karten) < min_cards_for_game:
        flash(f"Dieses Lernset hat nicht genügend Karten für ein Zuordnungsspiel (mind. {min_cards_for_game} benötigt).", "warning")
        return redirect(url_for('view_lernset', set_id=set_id))

    # Karten für die Anzeige vorbereiten (eine Liste bleibt in Originalreihenfolge für Begriffe, die andere wird für Definitionen gemischt)
    # Wichtig: Wir übergeben die Original-IDs, damit das JS sie matchen kann.

    karten_shuffled_for_terms = karten[:] # Eine Kopie für die Begriffe (Reihenfolge kann auch gemischt werden)
    random.shuffle(karten_shuffled_for_terms)

    definitions_shuffled = karten[:] # Eine weitere Kopie für die Definitionen
    random.shuffle(definitions_shuffled)

    # Stellen sicher, dass wir nicht versehentlich schon eine perfekte Übereinstimmung in der Reihenfolge haben,
    # obwohl das bei getrennten Listen für Begriffe und Definitionen weniger ein Problem ist,
    # solange die JS Logik IDs vergleicht.

    return render_template('matching_game.html',
                           lernset=lernset,
                           karten_shuffled=karten_shuffled_for_terms, # Wird für die Anzeige der Begriffe verwendet
                           definitions_shuffled=definitions_shuffled) # Wird für die Anzeige der Definitionen verwendet


if __name__ == '__main__':
    # Sicherstellen, dass die Datendatei beim ersten Start initialisiert wird, falls nicht vorhanden
    # data_manager.load_data() # Dies stellt sicher, dass data.json existiert oder erstellt wird.
    # Die load_data() Funktion in data_manager.py kümmert sich bereits darum.
    # Ein expliziter Aufruf hier ist nicht mehr zwingend nötig, wenn jede Route, die Daten braucht, sie lädt.
    # Aber es schadet auch nicht, es hier einmal beim Start zu tun.
    if not os.path.exists(data_manager.DATA_FILE):
        data_manager.save_data({"lernsets": []}) # Stellt sicher, dass eine leere Datei existiert

    app.run(debug=True)
