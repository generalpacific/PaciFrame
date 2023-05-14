import csv
import openai
import os

openai.api_key = os.environ["OPENAI_API_KEY"]

PAINTINGS = ["MONA LISA BY LEONARDO DA VINCI", "THE BIRTH OF VENUS BY SANDRO BOTTICELLI",
             "THE CREATION OF ADAM BY MICHELANGELO BUONARROTI", "THE LAST SUPPER BY LEONARDO DA VINCI",
             "THE ANCIENT OF DAYS BY WILLIAM BLAKE", "GIRL WITH A PEARL EARRING BY JOHANNES VERMEER",
             "THE NIGHT WATCH BY REMBRANDT VAN RIJN", "LANDSCAPE WITH THE FALL OF ICARUS BY PIETER BRUEGEL THE ELDER",
             "THE SCHOOL OF ATHENS BY RAFFAELLO SANTI", "LAS MENINAS BY DIEGO VELÁZQUEZ",
             "THE RETURN OF THE PRODIGAL SON BY REMBRANDT VAN RIJN", "THE PERSISTENCE OF MEMORY BY SALVADOR DALÍ",
             "THE TOWER OF BABEL BY PIETER BRUEGEL THE ELDER",
             "GEOPOLITICUS CHILD WATCHING THE BIRTH OF THE NEW MAN BY SALVADOR DALÍ", "THE KISS BY GUSTAV KLIMT",
             "IMPRESSION, SUNRISE BY CLAUDE MONET", "THE SCREAM BY EDVARD MUNCH",
             "THE STARRY NIGHT BY VINCENT VAN GOGH", "THE GREAT WAVE OF KANAGAWA BY KATSUSHIKA HOKUSAI",
             "SOUVENIR FROM HAVRE BY PABLO PICASSO"]

STAGING_PAINTING = ["MONA LISA BY LEONARDO DA VINCI", "THE TOWER OF BABEL BY PIETER BRUEGEL THE ELDER"]


def generate_prompt(painting):
    return '''A painting can be classified into:
                Style
                Medium
                Color palette
                Objects
                Theme in 5 words or less

                Classify {}'''.format(painting)


def generate_text(painting, model):
    prompt = generate_prompt(painting)
    completion = openai.ChatCompletion.create(model=model, messages=[{"role": "user", "content": prompt}])
    answer = completion.choices[0].message.content
    return answer


def parse_answer(answer, painting_metadata_dict):
    for line in answer.split('\n'):
        # split each line into key-value pairs
        line = line.lower().strip()
        key, value = line.split(': ')
        try:
            # store the key-value pairs in the dictionary
            painting_metadata_dict[key].append(value)
        except KeyError:
            print("Key not found: " + key + ". Continuing.")


def write_to_csv(painting_metadata_dict):
    # Open a new CSV file for writing
    with open('metadata.csv', 'w', newline='') as file:
        writer = csv.writer(file)

        # Write the header row
        writer.writerow(painting_metadata_dict.keys())

        # Write each row of data
        for row in zip(*painting_metadata_dict.values()):
            writer.writerow(row)


def main():
    model = "gpt-3.5-turbo"
    painting_metadata_dict = {"style": [], "medium": [], "color palette": [], "objects": [], "theme": []}
    for painting in PAINTINGS:
        print("classifying {}".format(painting))
        answer = generate_text(painting, model)
        print(answer)
        parse_answer(answer, painting_metadata_dict)
    print("Final dictionary: " + str(painting_metadata_dict))
    print("Writing to csv")
    write_to_csv(painting_metadata_dict)
    print("Done writing to csv")


if __name__ == '__main__':
    main()
